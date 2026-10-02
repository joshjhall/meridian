"""The one live LLM step (#4): complexity signals read from a claim's notes and transcript.

Making the model's output safe to act on is the work here, not the call:

- Names, policy numbers and claim numbers are masked before anything leaves the process.
- Output is structured only: a JSON schema on the request, then strict Pydantic validation
  here. Anything else, including an extra field, is rejected.
- The schema has no approve, deny or recommendation field. A signal can raise the tier
  (and so the claim's priority); it can never lower it or decide anything.
- Every signal quotes its source. Code checks the quote is in that document; a quote
  that isn't is marked unverified and ignored for routing. The check proves the passage
  exists, not that it supports the signal ("No injuries." is a real quote); that
  judgment stays with the adjuster, who sees every quote beside its signal.
- One call, 20s, no retries. On any failure the recorded response for the claim loads,
  goes through the same checks, and is marked as a fallback.

Endpoint and credentials come from the environment, read by the SDK itself:
ANTHROPIC_BASE_URL (unset means api.anthropic.com), and ANTHROPIC_AUTH_TOKEN or
ANTHROPIC_API_KEY. LLM_MODEL overrides the model.
"""

import hashlib
import json
import logging
import os
import re
import time
from typing import Any
from urllib.parse import urlsplit

import anthropic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fixtures import DATA, REPO
from models import Claim, SignalItem, SignalKind, Signals, Skill, Tier

log = logging.getLogger(__name__)

RECORDED_DIR = DATA / "recorded"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_BASE_URL = "https://api.anthropic.com"
TIMEOUT_S = 20.0
# Shorter than this and a "quote" matches almost anything.
MIN_QUOTE_CHARS = 12


# --- What the model may return ---


class LlmSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SignalKind
    skill: Skill | None = Field(
        default=None, description="Only for kind=secondary_skill: the second skill needed."
    )
    quote: str = Field(
        max_length=300, description="Verbatim passage from the source document, copied exactly."
    )
    source: str = Field(description="File name of the document the quote is from.")
    confidence: float = Field(ge=0, le=1)


class LlmSignalsResponse(BaseModel):
    """No approve, deny or recommendation field: by construction, the model can't decide."""

    model_config = ConfigDict(extra="forbid")

    signals: list[LlmSignal] = Field(max_length=12)
    suggested_tier: Tier | None = Field(
        default=None, description="A higher handling tier, if the text shows more complexity."
    )


class Recorded(BaseModel):
    """A response saved from an earlier run: what replay and the fallback use."""

    model: str
    response: LlmSignalsResponse


SYSTEM = """You read commercial auto insurance claim documents for complexity signals \
that the structured fields miss, so the claim reaches the right adjuster.

Signal kinds:
- injury: a bodily injury is claimed or described.
- onset_gap: time between the loss and first treatment, or symptoms reported late.
- causation_gap: the documents don't clearly link the damage or injury to the loss.
- dispute: the parties' accounts of the loss conflict.
- low_confidence: a passage of the auto-generated transcript or OCR is unreliable \
(marked [*] or [inaudible]) on a fact that matters.
- secondary_skill: the claim needs a second skill besides its type; set `skill`.

Rules:
- Every signal quotes the document it rests on, copied character for character, \
and names that document's file name as `source`. No quote, no signal.
- You describe evidence for a person to judge. You never approve, deny, or recommend \
an outcome, and you don't assess coverage or fault.
- Names and identifiers appear masked as [CLAIMANT], [POLICYHOLDER], [POLICY_NUMBER] \
and [CLAIM_ID]. Leave them masked.
- If nothing in the documents is a signal, return an empty list."""


def _prompt_digest() -> str:
    schema = json.dumps(anthropic.transform_schema(LlmSignalsResponse), sort_keys=True)
    return hashlib.sha256((SYSTEM + schema).encode()).hexdigest()[:8]


# Goes in every classify event and the audit drawer. v1.2 is the release history.json
# shows rolled back; this prompt is the next one. The digest changes with any edit to
# the prompt or the schema, so a record always names exactly what was sent.
PROMPT_VERSION = f"signals-prompt v1.3+{_prompt_digest()}"

# --- Inputs: the claim's documents, masked ---


def documents(claim: Claim) -> dict[str, str]:
    """File name → text: the claim's text documents, or its details for the synthetic ones."""
    docs: dict[str, str] = {}
    for rel in claim.sources:
        path = REPO / rel
        if rel.startswith("sample_claims/") and path.suffix in {".md", ".txt"} and path.exists():
            docs[path.name] = path.read_text()
    if not docs:
        lines = [f"{k}: {v}" for k, v in _flatten(claim.details)]
        docs["claim_details.txt"] = "\n".join(lines)
    return docs


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(value, dict):
        return [kv for k, v in value.items() for kv in _flatten(v, f"{prefix}{k}.")]
    if isinstance(value, list):
        return [kv for i, v in enumerate(value) for kv in _flatten(v, f"{prefix}{i}.")]
    return [(prefix.rstrip("."), str(value))]


# Fax OCR swaps letters and digits ("G10RIA", "CA-CA-88l23-l8"), so names and numbers
# are matched with the characters OCR confuses them with.
LOOKALIKES = {
    "o": "o0", "0": "0o", "i": "il1|!", "l": "l1i|", "1": "1li|", "s": "s5", "5": "5s",
    "b": "b8", "8": "8b", "g": "g6", "6": "6g", "z": "z2", "2": "2z", "d": "do0",
}  # fmt: skip
CORPORATE_SUFFIX = re.compile(r"[,\s]+(Inc|LLC|Ltd|Corp|Co)\.?$", re.IGNORECASE)
SUFFIX = r"(?:[,\s]+(?:[i1l]nc|llc|ltd|corp|co)\b\.?)?"
CLAIM_NUMBER = re.compile(r"\b(?:IS-CLM-|CLMT-)?\d{10}\b", re.IGNORECASE)
POLICY_NUMBER = re.compile(r"\b[A-Z]{2}-[A-Z]{2}-[\dlIO]{4,6}-[\dlIO]{2}\b", re.IGNORECASE)


def _fuzzy(value: str) -> str:
    """A pattern for `value`: any case, OCR confusions, any run of separators between words."""
    out = []
    for ch in value.lower():
        if ch.isspace() or ch in "*,":
            out.append(r"[\s*,]+")
        elif alts := LOOKALIKES.get(ch):
            out.append("[" + re.escape(alts) + "]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def _sub(pattern: str, token: str, text: str) -> str:
    return re.sub(rf"(?<![\w-]){pattern}(?![\w-])", token, text, flags=re.IGNORECASE)


def mask(text: str, claim: Claim) -> str:
    """Masks the claim's people and identifiers, and anything shaped like one."""
    d = claim.details
    if holder := d.get("policyholder"):
        core = CORPORATE_SUFFIX.sub("", holder)
        text = _sub(_fuzzy(core) + SUFFIX, "[POLICYHOLDER]", text)
    if claimant := d.get("claimant"):
        parts = claimant.split()
        # Full name either way round ("MENDEZ*GLORIA" in EDI), then each part alone
        # ("Mr. Ellison", "clmt Ellison").
        for name in (claimant, " ".join(reversed(parts)), *(p for p in parts if len(p) > 2)):
            text = _sub(_fuzzy(name), "[CLAIMANT]", text)
    if policy := d.get("policy_number"):
        text = _sub(_fuzzy(policy), "[POLICY_NUMBER]", text)
    text = CLAIM_NUMBER.sub("[CLAIM_ID]", text)
    return POLICY_NUMBER.sub("[POLICY_NUMBER]", text)


def masked_documents(claim: Claim) -> dict[str, str]:
    return {name: mask(text, claim) for name, text in documents(claim).items()}


def prompt(claim: Claim, docs: dict[str, str]) -> str:
    fields = (
        f"Claim type: {claim.claim_type}\nLoss state: {claim.state}\n"
        f"Intake channel: {claim.intake_channel}\nComplexity: {claim.complexity}"
    )
    body = "\n\n".join(f'<document name="{n}">\n{t}\n</document>' for n, t in docs.items())
    return f"{fields}\n\n{body}\n\nList the complexity signals in these documents."


# --- Checks on what comes back ---


# Models often straighten or curl quotes and dashes when copying; that isn't fabrication.
TYPOGRAPHY = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"}
)


def _norm(text: str) -> str:
    """Case, whitespace and typographic quotes and dashes don't count; every word does."""
    return re.sub(r"\s+", " ", text.translate(TYPOGRAPHY)).strip().casefold()


def verify(response: LlmSignalsResponse, docs: dict[str, str]) -> list[SignalItem]:
    """A signal is verified only if its quote is in the document it names."""
    normed = {name: _norm(text) for name, text in docs.items()}
    items = []
    for s in response.signals:
        quote = _norm(s.quote)
        found = len(quote) >= MIN_QUOTE_CHARS and quote in normed.get(s.source, "")
        items.append(SignalItem(**s.model_dump(), verified=found))
    return items


TIER_RANK = {Tier.T1: 1, Tier.T2: 2, Tier.T3: 3}


def to_signals(response: LlmSignalsResponse, docs: dict[str, str], **meta: Any) -> Signals:
    """What routing may read: only verified signals count."""
    items = verify(response, docs)
    ok = [i for i in items if i.verified]
    skills = [i.skill for i in ok if i.kind == "secondary_skill" and i.skill]
    return Signals(
        secondary_skills=list(dict.fromkeys(skills)),
        injury=any(i.kind == "injury" for i in ok),
        # A tier suggestion with no verified evidence behind it is ignored.
        suggested_tier=response.suggested_tier if ok else None,
        # The weakest verified signal bounds the step's confidence.
        confidence=min((i.confidence for i in ok), default=1.0),
        items=items,
        **meta,
    )


# --- Recorded responses ---


def recorded(claim_id: str) -> Recorded | None:
    path = RECORDED_DIR / f"{claim_id}.json"
    if not path.exists():
        return None
    return Recorded.model_validate_json(path.read_text())


def from_recorded(claim: Claim) -> Signals:
    """Replay and batch runs: the saved response, through the same checks as a live one."""
    saved = recorded(claim.claim_id)
    if saved is None:
        return Signals(source="rules")
    return to_signals(
        saved.response, masked_documents(claim), source="recorded", llm_model=saved.model
    )


# --- The live call ---


def model_name() -> str:
    return os.environ.get("LLM_MODEL") or DEFAULT_MODEL


def base_url_host() -> str:
    """The host the call goes to: the gateway if ANTHROPIC_BASE_URL is set."""
    return urlsplit(os.environ.get("ANTHROPIC_BASE_URL") or DEFAULT_BASE_URL).netloc


def live_available() -> bool:
    """Credentials are configured; without them every live call falls back."""
    return bool(os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))


def log_endpoint() -> None:
    """Startup line: where live calls go, and whether they can. Never the token."""
    log.info(
        "complexity signals: model %s via %s (%s)",
        model_name(),
        base_url_host(),
        "credentials set" if live_available() else "no credentials, recorded fallback only",
    )


def make_client() -> anthropic.Anthropic:
    # The SDK reads ANTHROPIC_BASE_URL and the credentials itself. No retries: a
    # second try would blow the 20s budget, and the fallback is the retry.
    return anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=0)


class LiveCallError(Exception):
    """The response came back but can't be used."""


def call(client: Any, claim: Claim, docs: dict[str, str]) -> tuple[LlmSignalsResponse, str]:
    response = client.messages.create(
        model=model_name(),
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt(claim, docs)}],
        # Low effort keeps the call well inside the 20s budget; this is extraction.
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": anthropic.transform_schema(LlmSignalsResponse),
            },
        },
    )
    if response.stop_reason != "end_turn":
        raise LiveCallError(f"stopped: {response.stop_reason}")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise LiveCallError("no text in the response")
    try:
        return LlmSignalsResponse.model_validate_json(text), response.model
    except ValidationError as e:
        raise LiveCallError(f"failed validation ({e.error_count()} errors)") from e


def _reason(e: Exception) -> str:
    match e:
        case anthropic.APITimeoutError():
            return f"timed out after {TIMEOUT_S:.0f}s"
        case anthropic.APIConnectionError():
            return f"could not reach {base_url_host()}"
        case anthropic.AuthenticationError() | anthropic.PermissionDeniedError():
            return "credentials rejected"
        case anthropic.APIStatusError():
            return f"API error {e.status_code}"
        case LiveCallError():
            return str(e)
        case TypeError() if "authentication" in str(e):
            return "no credentials"
        case _:
            return type(e).__name__


def run_live(claim: Claim, client: Any = None) -> Signals:
    """One live call for one claim. Any failure loads the recorded response instead."""
    docs = masked_documents(claim)
    host = base_url_host()
    # Latency is real elapsed time for the network call, not a demo-clock timestamp.
    started = time.perf_counter()
    try:
        response, model = call(client or make_client(), claim, docs)
    except Exception as e:  # every failure has the same safe answer: the recorded run
        reason = _reason(e)
        log.warning("complexity signals for %s fell back: %s", claim.claim_id, reason)
        saved = recorded(claim.claim_id)
        meta: dict[str, Any] = {
            "source": "llm_fallback",
            "fallback": True,
            "fallback_reason": reason,
            "base_url_host": host,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
        if saved is None:
            return Signals(**meta)
        return to_signals(saved.response, docs, llm_model=saved.model, **meta)
    latency = round((time.perf_counter() - started) * 1000)
    return to_signals(
        response, docs, source="llm", llm_model=model, latency_ms=latency, base_url_host=host
    )
