"""View data for the Chrome side panel (#11).

Every claim's panel has the same six sections (docs/presentation/panel_examples.md);
what fills them changes with the claim. The header and the pipeline's "Needs
attention" items are computed by running the pipeline; the wording of each claim's
points, its key facts and its contents is written per claim in
`data/panel/{claim_id}.json`, every point linked to its source.

The panel shows evidence for a person to judge. It never recommends approving or
denying a claim, and nothing it does writes a decision to ClaimsPro.
"""

import difflib
from collections import deque
from datetime import datetime
from functools import cache, lru_cache

from claimspro_page import SCREENS, documents, slugify

from fixtures import DATA, load_claim_fixtures, load_roster
from models import (
    AttentionItem,
    CorrectionLogEntry,
    FooterTouch,
    KeyFacts,
    OcrCheck,
    OcrDiff,
    OcrWord,
    PanelContent,
    PanelFooter,
    PanelHeader,
    PanelSummary,
    SourceRef,
)
from pipeline import PIPELINE_VERSION, PipelineResult, run_pipeline
from pipeline.intake import check_correction, fold, is_negation

PANEL_DATA = DATA / "panel"

# Section ids double as the anchors the "this is wrong" flag and the tests use.
SECTIONS: list[tuple[str, str]] = [
    ("header", "Header"),
    ("what-matters", "What matters"),
    ("key-facts", "Key facts"),
    ("needs-attention", "Needs attention"),
    ("contents", "Contents"),
    ("footer", "Footer"),
]


@cache
def load_content(claim_id: str) -> PanelContent | None:
    path = PANEL_DATA / f"{claim_id}.json"
    if not path.exists():
        return None
    return PanelContent.model_validate_json(path.read_text())


@lru_cache(maxsize=2)
def _pipeline(now: datetime) -> PipelineResult:
    # No sim: the panel reads the routing outcome; it never writes to ClaimsPro.
    # Kept for the latest clock times only; callers must treat the result as read-only.
    claims = [f.claim for f in load_claim_fixtures().values()]
    return run_pipeline(claims, load_roster(), now=now)


def ocr_diff(check: OcrCheck) -> OcrDiff:
    """Align raw and corrected words; the guard decides whether a person must look.

    Words align on the guard's own folding, so "n0t" pairs with "not". A word only on
    the raw side was dropped (corrected is ""); one only on the corrected side was
    added (raw is ""). A negation is marked on whichever side holds it.
    """
    raw, corrected = check.raw.split(), check.corrected.split()
    matcher = difflib.SequenceMatcher(
        a=[fold(w) for w in raw], b=[fold(w) for w in corrected], autojunk=False
    )
    words: list[OcrWord] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            words += [
                OcrWord(raw=r, corrected=c, negation=is_negation(c))
                for r, c in zip(raw[i1:i2], corrected[j1:j2], strict=True)
            ]
            continue
        words += [OcrWord(raw=r, corrected="", negation=is_negation(r)) for r in raw[i1:i2]]
        words += [OcrWord(raw="", corrected=c, negation=is_negation(c)) for c in corrected[j1:j2]]
    verdict = check_correction(check.raw, check.corrected)
    return OcrDiff(source=check.source, words=words, verdict=verdict)


def _linked(ref: SourceRef, anchors: set[str]) -> SourceRef:
    """Point a source at its ClaimsPro screen or document so the link can navigate there.

    The pipeline cites a file and sometimes a page ("estimate p.3"); the page moves into
    the label and the anchor becomes the document's.
    """
    if ref.anchor in anchors:
        return ref
    page = f", {ref.anchor}" if ref.anchor else ""
    doc = f"documents/{slugify(ref.path)}"
    return ref.model_copy(
        update={"label": ref.label + page, "anchor": doc if doc in anchors else "documents"}
    )


def build_summary(claim_id: str, now: datetime) -> PanelSummary | None:
    """The claim's panel, or None if it isn't one of the six demo claims."""
    fixture = load_claim_fixtures().get(claim_id)
    content = load_content(claim_id)
    routed = _pipeline(now).by_id().get(claim_id)
    if fixture is None or content is None or routed is None or routed.claim is None:
        return None
    claim = routed.claim
    audit = routed.audit
    regulation = routed.regulation
    tier = audit.tier or fixture.expected.tier

    anchors = {a for a, _ in SCREENS} | {d.anchor for d in documents(claim)}
    attention: list[AttentionItem] = [
        item.model_copy(update={"sources": [_linked(r, anchors) for r in item.sources]})
        for item in routed.attention
    ]
    attention += content.needs_attention
    if content.ocr_check is not None:
        attention.append(
            AttentionItem(
                kind="conflict",
                label=content.ocr_check.label,
                sources=[content.ocr_check.source],
                ocr_diff=ocr_diff(content.ocr_check),
            )
        )

    unusual = any(f.unusual for f in content.key_facts)
    touches = [
        FooterTouch(actor=f"Received ({claim.intake_channel})", at=claim.received_at),
        FooterTouch(actor="Pre-processing pipeline", at=now),
    ]
    if routed.adjuster_id:
        touches.append(FooterTouch(actor=f"Assigned to {routed.adjuster_id}", at=now))
    return PanelSummary(
        header=PanelHeader(
            claim_id=claim.claim_id,
            skills=audit.skills or fixture.expected.skills,
            tier=tier,
            sla_due_at=claim.sla_due_at,
            sla_state=claim.sla_state(now),
            regulated=bool(regulation and regulation.regulated),
            routing_reason=claim.routing_reason or fixture.expected.routing_reason,
            adjuster_id=routed.adjuster_id,
            synthetic=claim.synthetic,
        ),
        what_matters=content.what_matters,
        key_facts=KeyFacts(
            template=claim.claim_type,
            facts=content.key_facts,
            collapsed=not unusual and not content.timeline and not content.accounts,
            timeline=content.timeline,
            accounts=content.accounts,
        ),
        needs_attention=attention,
        contents=content.contents,
        footer=PanelFooter(
            touches=touches, pipeline_version=PIPELINE_VERSION, note=content.footer_note
        ),
        fast_lane=claim.review_lane == "fast_lane",
    )


def sla_left(summary: PanelSummary, now: datetime) -> tuple[str, float]:
    """Time left on the 24h SLA as a label, and the fraction of the window used (0-1).

    The label rounds down, like a countdown: 5h59m reads "5h left", so it never shows
    more time than remains and agrees with the amber threshold (under 6h).
    """
    left = summary.header.sla_due_at - now
    seconds = left.total_seconds()
    used = min(max(1 - seconds / (24 * 3600), 0.0), 1.0)
    if seconds <= 0:
        over = int(-seconds // 3600)
        return (f"Breached {over}h ago" if over >= 1 else "Breached"), used
    if seconds < 3600:
        return f"{int(seconds // 60)}m left", used
    return f"{int(seconds // 3600)}h left", used


# --- Correction log ---
# In memory and capped, like the rest of the demo's state. The admin view (#9) reads
# it; a real deployment would authenticate it and persist it with the audit record.

LOG_LIMIT = 1000
_log: deque[CorrectionLogEntry] = deque(maxlen=LOG_LIMIT)


def log_correction(entry: CorrectionLogEntry) -> CorrectionLogEntry:
    _log.append(entry)
    return entry


def corrections(claim_id: str | None = None) -> list[CorrectionLogEntry]:
    return [e for e in _log if claim_id is None or e.claim_id == claim_id]


def clear_corrections() -> None:
    _log.clear()
