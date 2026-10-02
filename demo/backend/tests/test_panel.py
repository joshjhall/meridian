import json
import random
import re
from datetime import datetime, timedelta
from html import unescape

import panel
import pytest
from claimspro_page import SCREENS, documents, neighbours
from fastapi.testclient import TestClient

import clock
from app import app
from claimspro_sim import ClaimsProSim
from claimspro_sim.api import get_sim
from fixtures import DATA, load_claim_fixtures
from models import CorrectionLogEntry, OcrCheck, OcrWord, PanelSummary, SourceRef
from pipeline.intake import is_negation

SIX = list(load_claim_fixtures())
NOW = datetime(2025, 10, 15, 9, 0)  # clock.DEMO_START
EXTENSION = DATA.parent / "extension"


@pytest.fixture
def client():
    sim = ClaimsProSim(
        (f.claim for f in load_claim_fixtures().values()),
        sleep=lambda _s: None,
        now=lambda: NOW,
        rng=random.Random(7),
    )
    app.dependency_overrides[get_sim] = lambda: sim
    panel.clear_corrections()
    yield TestClient(app, headers={"X-Meridian-Panel": "1"})
    app.dependency_overrides.clear()
    panel.clear_corrections()


def summary(claim_id: str) -> PanelSummary:
    s = panel.build_summary(claim_id, NOW)
    assert s is not None
    return s


def text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def section_order(html: str) -> list[str]:
    wanted = {sid for sid, _ in panel.SECTIONS}
    return [
        sid
        for sid in re.findall(r'<(?:section|header|footer)[^>]*\bid="([^"]+)"', html)
        if sid in wanted
    ]


# --- The shared structure ---


@pytest.mark.parametrize("claim_id", SIX)
def test_every_claim_has_the_shared_structure(client, claim_id):
    html = client.get(f"/panel?claim={claim_id}").text
    order = section_order(html)
    required = ["header", "what-matters", "key-facts", "contents", "footer"]
    assert [s for s in order if s in required] == required
    assert ("needs-attention" in order) == bool(summary(claim_id).needs_attention)


@pytest.mark.parametrize("claim_id", SIX)
def test_header_matches_the_spec(claim_id):
    expected = load_claim_fixtures()[claim_id].expected
    h = summary(claim_id).header
    assert h.tier == expected.tier
    assert h.skills == expected.skills
    assert h.regulated == expected.regulated
    assert h.sla_state == expected.sla_in_demo


@pytest.mark.parametrize("claim_id", SIX)
def test_every_point_links_to_a_claimspro_anchor(claim_id):
    claim = load_claim_fixtures()[claim_id].claim
    anchors = {a for a, _ in SCREENS} | {d.anchor for d in documents(claim)}
    s = summary(claim_id)
    refs = [p.source for p in s.what_matters]
    refs += [r for f in s.key_facts.facts for r in f.sources]
    refs += [e.source for e in s.key_facts.timeline] + [a.source for a in s.key_facts.accounts]
    refs += [r for i in s.needs_attention for r in i.sources]
    refs += [c.location for c in s.contents]
    assert refs
    assert {r.anchor for r in refs} <= anchors


@pytest.mark.parametrize("claim_id", SIX)
def test_panel_never_recommends_approval_or_denial(client, claim_id):
    page = text(client.get(f"/panel?claim={claim_id}").text).lower()
    assert not re.search(r"\b(approv\w*|den(y|ied|ial)|recommend\w*|pay (in full|out))\b", page)


def test_synthetic_claims_are_labelled(client):
    for claim_id in SIX:
        synthetic = load_claim_fixtures()[claim_id].claim.synthetic
        assert ("Synthetic story" in client.get(f"/panel?claim={claim_id}").text) == synthetic


# --- Claim-specific shapes ---


def test_clean_claim_gets_a_short_panel(client):
    clean = client.get("/panel?claim=IS-CLM-2025000300").text
    assert 'id="needs-attention"' not in clean
    key_facts = clean[clean.index('id="key-facts"') : clean.index('id="contents"')]
    assert re.search(r"<details\s*>", key_facts)  # collapsed: no open attribute
    assert "Confirm intake is complete" in clean
    others = [
        len(text(client.get(f"/panel?claim={c}").text)) for c in SIX if c != "IS-CLM-2025000300"
    ]
    assert len(text(clean)) < min(others)


def test_thin_file_leads_with_missing_items(client):
    html = client.get("/panel?claim=IS-CLM-2025002043").text
    order = section_order(html)
    assert order.index("needs-attention") < order.index("what-matters")
    assert html.count("Request it") == 3


def test_other_claims_lead_with_what_matters(client):
    order = section_order(client.get("/panel?claim=IS-CLM-2025002993").text)
    assert order.index("what-matters") < order.index("needs-attention")


def test_2993_shows_raw_ocr_next_to_corrected_with_the_negation_highlighted(client):
    html = client.get("/panel?claim=IS-CLM-2025002993").text
    assert '<span class="neg">n0t</span>' in html
    assert '<span class="neg">not</span>' in html
    assert "The negation “not” is kept." in html
    assert 'class="drop"' not in html and 'class="add"' not in html
    # The pipeline's OCR/EDI conflicts are there too, with a suggestion to confirm.
    assert "CA-CA-88123-18" in html
    assert "Confirm suggested" in html


OCR_REF = SourceRef(label="Fax OCR", path="ocr_output.txt", anchor="documents/ocr-output")


def test_ocr_diff_pairs_character_fixes_word_for_word():
    diff = panel.ocr_diff(
        OcrCheck(label="note", raw="n0t c0nsistent", corrected="not consistent", source=OCR_REF)
    )
    assert diff.verdict.accepted
    assert [(w.raw, w.corrected, w.negation) for w in diff.words] == [
        ("n0t", "not", True),
        ("c0nsistent", "consistent", False),
    ]


def test_ocr_diff_marks_a_dropped_negation_on_the_raw_side():
    diff = panel.ocr_diff(
        OcrCheck(label="note", raw="n0t c0nsistent", corrected="consistent", source=OCR_REF)
    )
    assert not diff.verdict.accepted
    assert diff.verdict.reason == "negation changed"
    assert [(w.raw, w.corrected, w.negation) for w in diff.words] == [
        ("n0t", "", True),
        ("c0nsistent", "consistent", False),
    ]


def test_ocr_diff_marks_an_added_negation_on_the_corrected_side():
    diff = panel.ocr_diff(
        OcrCheck(label="note", raw="c0nsistent", corrected="not consistent", source=OCR_REF)
    )
    assert not diff.verdict.accepted
    assert diff.words[0] == OcrWord(raw="", corrected="not", negation=True)
    assert (diff.words[1].raw, diff.words[1].corrected) == ("c0nsistent", "consistent")


@pytest.mark.parametrize(
    ("raw", "corrected", "accepted", "negations"),
    [
        ("is n0t covered", "is now covered", False, [("n0t", "")]),  # a different word
        ("can't c0ver", "can cover", False, [("can't", "")]),  # contraction dropped
        ("n0t, c0vered", "not, covered", True, [("n0t,", "not,")]),  # punctuation kept
    ],
)
def test_ocr_diff_edge_cases(raw, corrected, accepted, negations):
    diff = panel.ocr_diff(OcrCheck(label="x", raw=raw, corrected=corrected, source=OCR_REF))
    assert diff.verdict.accepted is accepted
    assert [(w.raw, w.corrected) for w in diff.words if w.negation] == negations


@pytest.mark.parametrize(
    ("word", "negation"),
    [
        ("not", True),
        ("n0t", True),
        ("N0T,", True),
        ("don't", True),
        ("never", True),
        ("now", False),
        ("note", False),
        ("nothing", False),
    ],
)
def test_is_negation(word, negation):
    assert is_negation(word) is negation


@pytest.mark.parametrize(
    ("claim_id", "collapsed"),
    [("IS-CLM-2025000300", True), ("IS-CLM-2025004222", False), ("IS-CLM-2025004518", False)],
)
def test_key_facts_collapse_only_when_nothing_is_unusual(claim_id, collapsed):
    assert summary(claim_id).key_facts.collapsed is collapsed


def test_4222_has_an_injury_timeline_and_marked_transcript_spans(client):
    s = summary("IS-CLM-2025004222")
    assert [e.when for e in s.key_facts.timeline][:3] == ["Fri 9/19", "Fri 9/19", "Mon 9/22"]
    spans = [i for i in s.needs_attention if i.kind == "low_confidence"]
    assert len(spans) == 5
    html = client.get("/panel?claim=IS-CLM-2025004222").text
    assert 'aria-label="Injury timeline"' in html
    assert "Delaware Avenue" in html
    # The regenerate button (#38) shows only with credentials; both states are in
    # test_llm_signals.test_panel_shows_regenerate_only_when_live_is_available.


def test_4518_lays_accounts_side_by_side(client):
    html = client.get("/panel?claim=IS-CLM-2025004518").text
    assert html.count('class="account"') == 2
    assert "Fault is the adjuster's call." in html


def test_breached_sla_is_shown_red(client):
    html = client.get("/panel?claim=IS-CLM-2025000375").text
    assert 'data-sla="breached"' in html
    assert "Breached 6h ago" in html
    assert "review not needed" in html  # the calibration-sample footer note


@pytest.mark.parametrize(
    ("left", "label", "used"),
    [
        (timedelta(hours=20), "20h left", 4 / 24),
        (timedelta(hours=5, minutes=59), "5h left", 1 - (5 + 59 / 60) / 24),  # amber: under 6h
        (timedelta(minutes=59, seconds=59), "59m left", None),  # never "60m left"
        (timedelta(0), "Breached", 1.0),
        (timedelta(minutes=-30), "Breached", 1.0),
        (timedelta(hours=-6), "Breached 6h ago", 1.0),
        (timedelta(hours=30), "30h left", 0.0),  # clamped
    ],
)
def test_sla_label_counts_down_and_clamps(left, label, used):
    s = summary("IS-CLM-2025000300")
    now = s.header.sla_due_at - left
    got_label, got_used = panel.sla_left(s, now)
    assert got_label == label
    assert 0.0 <= got_used <= 1.0
    if used is not None:
        assert got_used == pytest.approx(used)


@pytest.mark.parametrize(
    ("left", "state"),
    [
        (timedelta(hours=6), "on_track"),
        (timedelta(hours=5, minutes=59), "at_risk"),
        (timedelta(0), "breached"),
    ],
)
def test_rendered_sla_turns_amber_under_6h(client, left, state):
    due = summary("IS-CLM-2025000300").header.sla_due_at
    clock.reset(due - left)
    try:
        html = client.get("/panel?claim=IS-CLM-2025000300").text
    finally:
        clock.reset()
    assert f'data-sla="{state}"' in html


def test_summary_is_stable_across_calls_and_clock_times():
    first = summary("IS-CLM-2025004222").model_dump()
    later = panel.build_summary("IS-CLM-2025004222", NOW + timedelta(hours=1))
    assert later is not None and later.header.sla_state == "at_risk"
    # Building another panel must not mutate the cached content or pipeline result.
    assert summary("IS-CLM-2025004222").model_dump() == first
    assert len(summary("IS-CLM-2025002993").needs_attention) == 6


# --- Unknown claims and the correction log ---


def test_unknown_or_missing_claim_offers_the_six(client):
    for url in ("/panel", "/panel?claim=IS-CLM-2025000095"):
        response = client.get(url)
        assert response.status_code == 200
        assert all(f"/panel?claim={c}" in response.text for c in SIX)


def test_malformed_claim_id_is_rejected(client):
    assert client.get("/panel?claim=nope").status_code == 422


def test_this_is_wrong_goes_to_the_correction_log(client):
    response = client.post("/panel/IS-CLM-2025000300/log?section=panel&action=flag")
    assert response.status_code == 200
    assert "Flagged for the correction log" in response.text
    client.post(
        "/panel/IS-CLM-2025002993/log?section=needs-attention&action=confirm&item=Policy+number"
    )
    log = client.get("/api/corrections").json()
    assert [(e["claim_id"], e["action"]) for e in log] == [
        ("IS-CLM-2025000300", "flag"),
        ("IS-CLM-2025002993", "confirm"),
    ]
    only = client.get("/api/corrections?claim=IS-CLM-2025002993").json()
    assert [e["item"] for e in only] == ["Policy number"]


@pytest.mark.parametrize(
    "query",
    [
        "section=",
        "section=" + "x" * 41,
        "section=panel&item=" + "x" * 201,
        "section=panel&note=" + "x" * 501,
    ],
)
def test_log_rejects_empty_or_oversize_fields(client, query):
    assert client.post(f"/panel/IS-CLM-2025000300/log?{query}").status_code == 422
    assert panel.corrections() == []


def test_picker_rejects_malformed_claim_ids_and_redirects_plainly(client):
    assert (
        client.get("/claimspro?claim=https://evil.example", follow_redirects=False).status_code
        == 422
    )
    response = client.get("/claimspro?claim=IS-CLM-2025000300", follow_redirects=False)
    assert response.headers["location"] == "/claimspro/IS-CLM-2025000300"


def test_correction_log_is_capped():
    for i in range(panel.LOG_LIMIT + 5):
        panel.log_correction(
            CorrectionLogEntry(
                claim_id="IS-CLM-2025000300", section="panel", action="flag", note=str(i), at=NOW
            )
        )
    log = panel.corrections()
    assert len(log) == panel.LOG_LIMIT
    assert log[0].note == "5"


def test_log_rejects_unknown_claims_and_actions(client):
    assert client.post("/panel/IS-CLM-2025000095/log?section=panel").status_code == 404
    assert (
        client.post("/panel/IS-CLM-2025000300/log?section=panel&action=approve").status_code == 422
    )


def test_log_needs_the_panel_header(client):
    # Blocks a cross-site form posting to the log (CSRF).
    bare = TestClient(app)
    assert bare.post("/panel/IS-CLM-2025000300/log?section=panel").status_code == 403
    assert "X-Meridian-Panel" in client.get("/panel?claim=IS-CLM-2025000300").text


# --- Docked fallback and the extension shell ---


def test_docked_fallback_reserves_space_instead_of_overlaying(client):
    html = client.get("/claimspro/IS-CLM-2025004222?panel=docked").text
    assert "body { margin-right: 420px; }" in html
    assert "#docked-panel { position: fixed; top: 0; right: 0; width: 420px;" in html
    assert 'src="/panel?claim=IS-CLM-2025004222"' in html
    prev_id, next_id = neighbours("IS-CLM-2025004222")
    assert f'href="/claimspro/{prev_id}?panel=docked"' in html
    assert f'href="/claimspro/{next_id}?panel=docked"' in html


def test_mock_page_has_no_panel_unless_docked(client):
    html = client.get("/claimspro/IS-CLM-2025004222").text
    assert "<iframe" not in html
    assert "<style" not in html


def test_picker_keeps_the_dock(client):
    response = client.get("/claimspro?claim=IS-CLM-2025000300&panel=docked", follow_redirects=False)
    assert response.headers["location"] == "/claimspro/IS-CLM-2025000300?panel=docked"


ANCHOR_CHECK = "/^[a-z0-9/-]{1,80}$/"


@pytest.mark.parametrize("claim_id", SIX)
def test_every_panel_anchor_passes_the_hosts_navigation_check(claim_id):
    # Both hosts (extension shell, docked mock page) drop navigate messages whose
    # anchor fails this check; every anchor the panel links to must pass it.
    html = TestClient(app).get(f"/panel?claim={claim_id}").text
    anchors = re.findall(r'data-nav="([^"]+)"', html)
    assert anchors
    assert all(re.fullmatch(r"[a-z0-9/-]{1,80}", a) for a in anchors)


def test_both_hosts_validate_navigate_messages(client):
    docked = client.get("/claimspro/IS-CLM-2025004222?panel=docked").text
    extension = (EXTENSION / "panel.js").read_text()
    for host in (docked, extension):
        assert ANCHOR_CHECK in host
        assert "IS-CLM-\\d{10}" in host


def test_extension_is_a_side_panel_with_no_page_injection():
    manifest = json.loads((EXTENSION / "manifest.json").read_text())
    assert manifest["manifest_version"] == 3
    assert manifest["side_panel"]["default_path"] == "panel.html"
    assert "content_scripts" not in manifest
    assert "scripting" not in manifest["permissions"]
    shell = (EXTENSION / "panel.html").read_text()
    # MV3 forbids inline scripts in extension pages.
    assert re.findall(r"<script[^>]*>(.*?)</script>", shell, re.S) == [""]
    assert 'src="panel.js"' in shell
