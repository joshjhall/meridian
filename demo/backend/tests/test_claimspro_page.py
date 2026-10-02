import random
import re
from datetime import datetime, timedelta

import pytest
from claimspro_page import (
    EMPTY,
    NOT_SAVED,
    SCREENS,
    custom_field_rows,
    details_by_screen,
    documents,
    neighbours,
    slugify,
)
from fastapi.testclient import TestClient

from app import app
from claimspro_sim import ClaimsProSim, reliable_write
from claimspro_sim.api import get_sim
from fixtures import load_claim_fixtures

SIX = list(load_claim_fixtures())
NOW = datetime(2025, 10, 15, 9, 0)
EXTRACT_CLAIM = "IS-CLM-2025000095"  # an open extract claim, not one of the six


@pytest.fixture
def sim() -> ClaimsProSim:
    return ClaimsProSim(
        (f.claim for f in load_claim_fixtures().values()),
        sleep=lambda _s: None,
        now=lambda: NOW,
        rng=random.Random(7),
    )


@pytest.fixture
def client(sim: ClaimsProSim):
    app.dependency_overrides[get_sim] = lambda: sim
    yield TestClient(app)
    app.dependency_overrides.clear()


def custom_fields_block(html: str) -> str:
    start = html.index('id="custom-fields"')
    return html[start : html.index("</fieldset>", start)]


def ids(html: str) -> set[str]:
    return set(re.findall(r'id="([^"]+)"', html))


@pytest.mark.parametrize("claim_id", SIX)
def test_every_claim_renders_fields_screens_and_documents(client, claim_id):
    claim = load_claim_fixtures()[claim_id].claim
    response = client.get(f"/claimspro/{claim_id}")
    assert response.status_code == 200
    html = response.text
    assert claim.claim_type in html
    assert {anchor for anchor, _ in SCREENS} <= ids(html)
    docs = documents(claim)
    assert docs, f"{claim_id} lists no documents"
    assert {d.anchor for d in docs} <= ids(html)


def test_anchors_named_in_the_panel_spec_exist(client):
    # panel_examples.md: 4222's timeline cites the medical summary; 2993's conflicts
    # cite the OCR output and EDI record.
    assert "documents/medical-summary" in ids(client.get("/claimspro/IS-CLM-2025004222").text)
    html = client.get("/claimspro/IS-CLM-2025002993").text
    assert {"documents/ocr-output", "documents/edi-record"} <= ids(html)


def test_custom_fields_show_values_written_to_the_simulator(client, sim):
    claim_id = "IS-CLM-2025004222"
    sim.soap.UpdateCustomFields(
        claim_id,
        {"tier": "T3", "routing_reason": "BI over $10K in NY → T3 senior first"},
        idempotency_key="k1",
    )
    sim.store.set_write_status(claim_id, "confirmed")
    html = client.get(f"/claimspro/{claim_id}").text
    assert "T3 senior" in html
    assert "BI over $10K in NY → T3 senior first" in html
    assert NOT_SAVED not in html


def test_custom_fields_read_not_yet_saved_while_a_write_is_pending(client, sim):
    claim_id = "IS-CLM-2025000300"
    sim.soap.UpdateCustomFields(claim_id, {"tier": "T1"}, idempotency_key="k1")
    sim.store.set_write_status(claim_id, "pending")
    html = client.get(f"/claimspro/{claim_id}").text
    fields = custom_fields_block(html)
    assert fields.count(NOT_SAVED) == 5  # every written field; SLA due is derived
    assert "T1 standard" not in fields


def test_custom_fields_flag_a_failed_save_and_a_breached_sla():
    claim = load_claim_fixtures()["IS-CLM-2025000375"].claim.model_copy(
        update={"write_status": "write_failed"}
    )
    rows = dict(custom_field_rows(claim, claim.sla_due_at + timedelta(minutes=1)))
    assert rows["Last save"] == "SAVE FAILED"
    assert rows["SLA due"].endswith("(BREACHED)")
    assert rows["Tier"] == EMPTY  # not routed yet


@pytest.mark.parametrize(
    ("hours_left", "label"), [(12, "(on track)"), (2, "(AT RISK)"), (-1, "(BREACHED)")]
)
def test_sla_due_shows_its_state(hours_left, label):
    claim = load_claim_fixtures()[SIX[0]].claim
    rows = dict(custom_field_rows(claim, claim.sla_due_at - timedelta(hours=hours_left)))
    assert rows["SLA due"].endswith(label)


def test_a_reliable_write_shows_in_custom_fields_and_history(client, sim):
    claim_id = SIX[0]
    reliable_write(sim, "UpdateCustomFields", claim_id, {"fields": {"tier": "T1"}})
    html = client.get(f"/claimspro/{claim_id}").text
    history = html[html.index('id="history"') :]
    assert "No pipeline activity" not in history
    assert history.count(sim.events(claim_id)[0].pipeline_version) == len(sim.events(claim_id))
    fields = custom_fields_block(html)
    assert "T1 standard" in fields
    assert re.search(r"Last save</th>\s*<td>Saved</td>", fields)


def test_a_failed_write_shows_save_failed_on_the_page(client, sim):
    claim_id = SIX[0]
    sim.store.set_write_status(claim_id, "write_failed")
    fields = custom_fields_block(client.get(f"/claimspro/{claim_id}").text)
    assert re.search(r"Last save</th>\s*<td>SAVE FAILED</td>", fields)
    assert re.search(r"Tier</th>\s*<td>—</td>", fields)  # nothing routed yet


def test_documents_list_photos_and_survive_odd_names(client):
    clean = load_claim_fixtures()["IS-CLM-2025000300"].claim
    slugs = [d.slug for d in documents(clean)]
    assert {"img-0071", "img-0072"} <= set(slugs)
    odd = clean.model_copy(update={"sources": ["sample_claims/x/___.pdf"], "details": {}})
    assert [d.slug for d in documents(odd)] == ["document"]
    bare = clean.model_copy(update={"sources": [], "details": {}})
    assert documents(bare) == []


def test_prev_next_cycle_through_the_six_claims(client):
    assert neighbours(SIX[0]) == (SIX[-1], SIX[1])
    assert neighbours(SIX[-1]) == (SIX[-2], SIX[0])
    html = client.get(f"/claimspro/{SIX[2]}").text
    assert f'href="/claimspro/{SIX[1]}"' in html
    assert f'href="/claimspro/{SIX[3]}"' in html
    for claim_id in SIX:
        assert f'<option value="{claim_id}"' in html


def test_extract_claim_outside_the_six_renders():
    # The default simulator seeds the extract's open claims too (store.seed_claims).
    default_sim = ClaimsProSim(sleep=lambda _s: None)
    app.dependency_overrides[get_sim] = lambda: default_sim
    try:
        response = TestClient(app).get(f"/claimspro/{EXTRACT_CLAIM}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, f"{EXTRACT_CLAIM} no longer seeded by the simulator?"
    assert neighbours(EXTRACT_CLAIM) == (SIX[-1], SIX[0])
    assert f'href="/claimspro/{SIX[-1]}"' in response.text
    assert f'href="/claimspro/{SIX[0]}"' in response.text


def test_details_land_on_their_screens():
    screens = details_by_screen(load_claim_fixtures()["IS-CLM-2025000300"].claim)
    assert "policy_number" in screens["policy"]
    assert "estimate" in screens["payments"]
    assert "loss_description" in screens["loss"]  # unlisted keys go to Loss
    assert all("photos" not in fields for fields in screens.values())
    for claim_id, fixture in load_claim_fixtures().items():
        placed = [k for fields in details_by_screen(fixture.claim).values() for k in fields]
        assert sorted(placed) == sorted(set(fixture.claim.details) - {"photos"}), claim_id


def test_repeated_file_stems_get_unique_anchors():
    claim = load_claim_fixtures()["IS-CLM-2025000300"].claim.model_copy(
        update={"sources": ["sample_claims/x/report.pdf", "sample_claims/x/report.md"]}
    )
    slugs = [d.slug for d in documents(claim)]
    assert slugs[:2] == ["report", "report-2"]
    assert len(slugs) == len(set(slugs))


def test_notes_from_the_simulator_show_on_the_notes_screen(client, sim):
    claim_id = SIX[0]
    sim.soap.AddNote(claim_id, "Called the shop", author="ADJ-101", idempotency_key="n1")
    html = client.get(f"/claimspro/{claim_id}").text
    notes = html[html.index('id="notes"') : html.index('id="payments"')]
    assert "Called the shop" in notes


def test_picker_redirects_so_the_url_carries_the_claim(client):
    response = client.get(f"/claimspro?claim={SIX[1]}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/claimspro/{SIX[1]}"


def test_picker_rejects_anything_but_a_claim_id(client):
    response = client.get("/claimspro?claim=//evil.example", follow_redirects=False)
    assert response.status_code == 422


def test_unknown_claim_is_404(client):
    assert client.get("/claimspro/IS-CLM-0000000000").status_code == 404


def test_page_loads_no_stylesheet_or_script(client):
    html = client.get(f"/claimspro/{SIX[0]}").text.lower()
    for marker in ("basecoat", "tailwind", "<link", "<style", "<script", "/static/"):
        assert marker not in html


def test_slugify_uses_the_file_stem():
    assert slugify("sample_claims/IS-CLM-2025004222/medical_summary.pdf") == "medical-summary"
    assert slugify("IMG_0071.jpg") == "img-0071"
