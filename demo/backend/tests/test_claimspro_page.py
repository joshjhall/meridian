import random
import re
from datetime import datetime

import pytest
from claimspro_page import NOT_SAVED, SCREENS, documents, neighbours, slugify
from fastapi.testclient import TestClient

from app import app
from claimspro_sim import ClaimsProSim
from claimspro_sim.api import get_sim
from fixtures import load_claim_fixtures

SIX = list(load_claim_fixtures())
NOW = datetime(2025, 10, 15, 9, 0)


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
    fields = html[html.index('id="custom-fields"') : html.index("</fieldset>")]
    assert fields.count(NOT_SAVED) == 5  # every written field; SLA due is derived
    assert "T1 standard" not in fields


def test_prev_next_cycle_through_the_six_claims(client):
    assert neighbours(SIX[0]) == (SIX[-1], SIX[1])
    assert neighbours(SIX[-1]) == (SIX[-2], SIX[0])
    html = client.get(f"/claimspro/{SIX[2]}").text
    assert f'href="/claimspro/{SIX[1]}"' in html
    assert f'href="/claimspro/{SIX[3]}"' in html
    for claim_id in SIX:
        assert f'<option value="{claim_id}"' in html


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
