"""Intake quality: validate the record, cross-check fax OCR against EDI and arithmetic.

Everything here proposes; nothing is applied to the claim. A person confirms each
correction in the panel ("Needs attention"). The EDI parser drops ~12% of partner
submissions today; here a bad record becomes an exception with named reasons instead.
"""

import difflib
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fixtures import REPO, claim_from_row
from models import AttentionItem, Claim, CorrectionVerdict, SourceRef

# OCR confusables, folded to one canonical character so "n0t" and "not" compare equal
# but "not" and "now" do not.
_FOLD = str.maketrans({"0": "o", "1": "l", "i": "l", "|": "l", "5": "s", "8": "b"})
NEGATIONS = frozenset(w.translate(_FOLD) for w in ("no", "not", "never", "nor", "none", "without"))
# Characters OCR reads for a digit that can only be that digit; anything else is unreadable.
_DIGIT_FOR = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"})
_AMOUNT = r"[0-9OolIB,]+\.[0-9OolIB]{2}"
# Readable text for labels: digits OCR put in place of letters.
_DISPLAY = str.maketrans({"0": "o", "1": "l"})
LOW_OCR_CONFIDENCE = 0.8


def validate(raw: Claim | dict[str, Any]) -> tuple[Claim | None, list[str]]:
    """A Claim, or the named reasons a person must fix before it can be routed."""
    if isinstance(raw, Claim):
        return raw, []
    try:
        return claim_from_row(raw), []
    except ValidationError as e:
        return None, [
            f"{'.'.join(str(p) for p in err['loc']) or 'record'}: {err['msg']}"
            for err in e.errors()
        ]


def intake_gaps(claim: Claim) -> list[AttentionItem]:
    """Documents intake already knows are missing (carried in the claim's details)."""
    return [
        AttentionItem(kind="missing", label=str(item)) for item in claim.details.get("missing", [])
    ]


def check_correction(raw: str, corrected: str) -> CorrectionVerdict:
    """Accept a correction only if it changes characters, never words.

    Compares word by word after folding OCR confusables. Any dropped or added word is
    rejected and goes to a person; a dropped or added negation is called out by name.
    """
    before = raw.split()
    after = corrected.split()
    matcher = difflib.SequenceMatcher(
        a=[w.lower().translate(_FOLD) for w in before],
        b=[w.lower().translate(_FOLD) for w in after],
        autojunk=False,
    )
    dropped: list[str] = []
    added: list[str] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "equal":
            dropped += before[i1:i2]
            added += after[j1:j2]
    if not dropped and not added:
        return CorrectionVerdict(accepted=True, needs_person=False)
    changed = [w.lower().translate(_FOLD).strip(".,;:") for w in dropped + added]
    negation = any(w in NEGATIONS or w.endswith("n't") for w in changed)
    reason = "negation changed" if negation else "words changed"
    return CorrectionVerdict(
        accepted=False, needs_person=True, dropped=dropped, added=added, reason=reason
    )


# --- Fax OCR vs EDI cross-check ---


class UnreadableSource(ValueError):
    """A listed intake source can't be read; a person must look, not the pipeline."""


def ocr_cross_check(claim: Claim) -> list[AttentionItem]:
    """Conflicts between the fax OCR, the EDI record and the estimate's own arithmetic.

    Raises UnreadableSource when a listed source is missing, so the claim stops for a person.
    """
    ocr_path = _source(claim, "ocr_output.txt")
    edi_path = _source(claim, "edi_record.txt")
    if ocr_path is None or edi_path is None:
        return []
    try:
        ocr = (REPO / ocr_path).read_text()
        edi = _segments((REPO / edi_path).read_text())
    except OSError as e:
        raise UnreadableSource(f"intake source unreadable: {e.filename or e}") from e
    ocr_ref = SourceRef(label="Fax OCR", path=ocr_path)
    edi_ref = SourceRef(label="EDI 837", path=edi_path)
    items = [
        *_policy_number(ocr, edi, ocr_ref, edi_ref),
        *_line_item_arithmetic(ocr, ocr_ref),
        *_date_of_loss(ocr, edi, ocr_ref, edi_ref),
        *_claimant_contact(ocr, edi, ocr_ref, edi_ref),
    ]
    confidence = claim.details.get("ocr_confidence")
    if isinstance(confidence, int | float) and confidence < LOW_OCR_CONFIDENCE:
        items.append(
            AttentionItem(
                kind="low_confidence",
                label=f"Fax OCR confidence {confidence:.2f}",
                sources=[ocr_ref],
            )
        )
    return items


def _source(claim: Claim, name: str) -> str | None:
    return next((s for s in claim.sources if Path(s).name == name), None)


Segments = list[list[str]]


def _segments(edi: str) -> Segments:
    """X12 segments in order (element separator *, terminator ~), past the text header."""
    segments = [raw.strip().split("\n")[-1].split("*") for raw in edi.split("~")]
    return [s for s in segments if s[0]]


def _find(edi: Segments, segment_id: str, qualifier: str) -> list[str] | None:
    return next((s for s in edi if s[0] == segment_id and s[1:2] == [qualifier]), None)


def _loop(edi: Segments, entity: str) -> Segments:
    """The segments following an NM1 entity, up to the next NM1, HL or CLM."""
    start = next((i for i, s in enumerate(edi) if s[:2] == ["NM1", entity]), None)
    if start is None:
        return []
    rest = edi[start + 1 :]
    end = next((i for i, s in enumerate(rest) if s[0] in {"NM1", "HL", "CLM"}), len(rest))
    return rest[:end]


def _proposal(raw: str, suggested: str) -> str | None:
    """Only offer a suggestion the negation guard would accept as a character fix."""
    return suggested if check_correction(raw, suggested).accepted else None


def _policy_number(
    ocr: str, edi: Segments, ocr_ref: SourceRef, edi_ref: SourceRef
) -> list[AttentionItem]:
    insured = _find(edi, "NM1", "IL")
    if insured is None or len(insured) < 10:
        return []
    edi_policy = insured[9]
    for seen in dict.fromkeys(re.findall(r"P0?[Ll1][Ll1]?[Cc][Yy1]\s+([A-Z0-9Ol-]+-\S+)", ocr)):
        if seen != edi_policy:
            return [
                AttentionItem(
                    kind="conflict",
                    label="Policy number",
                    sources=[ocr_ref, edi_ref],
                    values=[f"fax: {seen}", f"EDI: {edi_policy}"],
                    suggested=_proposal(seen, edi_policy),
                )
            ]
    return []


def _amount(token: str) -> Decimal | None:
    """The amount if every character reads as one digit; None if any is unreadable."""
    try:
        return Decimal(token.translate(_DIGIT_FOR).replace(",", ""))
    except InvalidOperation:
        return None


def _section(ocr: str, title: str) -> str:
    match = re.search(rf"--- [^\n]*{title}[^\n]* ---\n(.*?)(?=\n---|\Z)", ocr, re.S)
    return match.group(1) if match else ""


def _line_item_arithmetic(ocr: str, ocr_ref: SourceRef) -> list[AttentionItem]:
    """Parts lines must add up to the recap's parts total; solve for the one unreadable line."""
    recap = re.search(rf"Parts\s+({_AMOUNT})", _section(ocr, "recap"))
    # A line: its number (one character), up to six words, the R&R operation, the amount.
    lines = re.findall(
        rf"(?<!\S)([0-9l])\s+((?:\S+\s+){{1,6}}?)R&R\s+({_AMOUNT})", _section(ocr, "line items")
    )
    total = _amount(recap.group(1)) if recap else None
    if total is None or not lines:
        return []
    readable = [a for _, _, raw in lines if (a := _amount(raw)) is not None]
    unreadable = [(n, d, raw) for n, d, raw in lines if _amount(raw) is None]
    if len(unreadable) != 1:
        return []
    _, description, raw = unreadable[0]
    solved = total - sum(readable, Decimal(0))
    shown = f"{solved:,.2f}"
    return [
        AttentionItem(
            kind="conflict",
            label=f"{description.strip().translate(_DISPLAY).capitalize()} line amount",
            sources=[ocr_ref.model_copy(update={"anchor": "estimate p.3"})],
            values=[f"fax: {raw}", f"line items sum to the recap parts total only at {shown}"],
            suggested=_proposal(raw, shown),
        )
    ]


def _date_of_loss(
    ocr: str, edi: Segments, ocr_ref: SourceRef, edi_ref: SourceRef
) -> list[AttentionItem]:
    """An accident date after the repair estimate was written is almost certainly receipt."""
    loss = _find(edi, "DTP", "439")
    written = re.search(r"Written\s+([0-9O]{4}-[0-9O]{2}-[0-9O]{2})", ocr)
    if loss is None or written is None:
        return []
    try:
        loss_date = datetime.strptime(loss[3], "%Y%m%d").date()
        estimate_date = date.fromisoformat(written.group(1).replace("O", "0"))
    except IndexError, ValueError:
        return [
            AttentionItem(
                kind="conflict",
                label="Date of loss unreadable; unverified",
                sources=[ocr_ref, edi_ref],
                values=[f"EDI: {'*'.join(loss)}", f"estimate: {written.group(1)}"],
            )
        ]
    if loss_date <= estimate_date:
        return []
    fax = re.search(r"D0?L\s+(\S+)", ocr)
    return [
        AttentionItem(
            kind="conflict",
            label="Date of loss likely receipt date; unverified",
            sources=[ocr_ref, edi_ref],
            values=[
                f"fax: {fax.group(1) if fax else 'unreadable'}",
                f"EDI: {loss_date.isoformat()}",
                f"estimate written {estimate_date.isoformat()}",
            ],
        )
    ]


def _claimant_contact(
    ocr: str, edi: Segments, ocr_ref: SourceRef, edi_ref: SourceRef
) -> list[AttentionItem]:
    on_fax = re.search(r"C[Ll1]A[Ll1]MANT\s+C0NTACT\s+([^_\s\[]\S*)", ocr)
    # EDI contact: a PER segment, or an N3 street address, in the claimant's own loop.
    in_edi = any(s[0] in {"PER", "N3"} and len(s) > 1 and s[1] for s in _loop(edi, "QC"))
    if on_fax or in_edi:
        return []
    return [
        AttentionItem(
            kind="missing",
            label="Claimant contact (phone chase)",
            sources=[ocr_ref, edi_ref],
            values=["fax: blank", "EDI: empty address, no contact"],
        )
    ]
