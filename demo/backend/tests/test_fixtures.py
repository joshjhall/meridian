import csv
import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import app
from fixtures import DATA, load_claim_fixtures, load_roster
from models import Adjuster, ClaimFixture, Skill, Tier

REPO = DATA.parents[1]
SIX = {
    "IS-CLM-2025000300", "IS-CLM-2025004222", "IS-CLM-2025002993",
    "IS-CLM-2025000375", "IS-CLM-2025004518", "IS-CLM-2025002043",
}
SYNTHETIC = {"IS-CLM-2025000375", "IS-CLM-2025004518", "IS-CLM-2025002043"}


def test_six_claim_fixtures_load_and_validate():
    fixtures = load_claim_fixtures()
    assert set(fixtures) == SIX
    assert {cid for cid, f in fixtures.items() if f.claim.synthetic} == SYNTHETIC


def test_fixture_numbers_match_extract():
    with (REPO / "reference" / "claims_processing.csv").open(newline="") as f:
        rows = {r["claim_id"]: r for r in csv.DictReader(f) if r["claim_id"] in SIX}
    assert set(rows) == SIX
    for cid, fixture in load_claim_fixtures().items():
        claim, row = fixture.claim, rows[cid]
        assert claim.claim_amount_usd == float(row["claim_amount_usd"])
        assert claim.queue_wait_hours == float(row["queue_wait_hours"])
        assert claim.requires_human_by_regulation == row["requires_human_by_regulation"]
        assert claim.adjuster_id == row["adjuster_id"]


def test_fixture_sources_exist():
    for fixture in load_claim_fixtures().values():
        assert fixture.claim.sources, fixture.claim.claim_id
        for src in fixture.claim.sources:
            assert (REPO / src).exists(), src


def test_sla_is_24h_from_receipt():
    for fixture in load_claim_fixtures().values():
        claim = fixture.claim
        assert (claim.sla_due_at - claim.received_at).total_seconds() == 24 * 3600


def test_roster_shape():
    roster = load_roster()
    assert len(roster) == 95
    assert len({a.id for a in roster}) == 95
    t3 = [a for a in roster if Tier.T3 in a.tiers]
    assert len(t3) == 16
    assert Counter(a.role for a in t3) == {"senior": 12, "lead": 4}
    assert all(Skill.BODILY_INJURY in a.skills for a in t3)
    assert sum(1 for a in roster if Tier.T3 not in a.tiers) == 79


def test_roster_covers_all_extract_adjuster_ids():
    with (REPO / "reference" / "claims_processing.csv").open(newline="") as f:
        extract_ids = {r["adjuster_id"] for r in csv.DictReader(f)}
    assert len(extract_ids) == 50
    assert extract_ids <= {a.id for a in load_roster()}


def test_roster_is_reproducible_from_seed(monkeypatch):
    monkeypatch.syspath_prepend(str(DATA))
    from gen_roster import build

    regenerated = [a.model_dump(mode="json") for a in build()]
    assert regenerated == json.loads((DATA / "roster.json").read_text())


def test_claim_fixtures_match_generator(monkeypatch):
    monkeypatch.syspath_prepend(str(DATA))
    from build_claims import build

    assert {f.claim.claim_id: f for f in build()} == load_claim_fixtures()


client = TestClient(app)


def test_api_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_api_lists_six_claims():
    assert {c["claim_id"] for c in client.get("/api/claims").json()} == SIX


def test_api_gets_claim_with_computed_sla():
    body = client.get("/api/claims/IS-CLM-2025004222").json()
    assert body["claim_type"] == "Bodily Injury"
    assert body["sla_due_at"].startswith("2025-09-26T10:00")


def test_api_unknown_claim_is_404():
    response = client.get("/api/claims/IS-CLM-0000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "unknown claim IS-CLM-0000000000"


def test_api_roster_entries_validate():
    body = client.get("/api/roster").json()
    assert len(body) == 95
    assert [Adjuster.model_validate(a) for a in body] == load_roster()


def test_invalid_fixture_is_rejected():
    raw = (DATA / "claims" / "IS-CLM-2025000300.json").read_text()
    with pytest.raises(ValidationError):
        ClaimFixture.model_validate_json(raw.replace('"Collision"', '"Hovercraft"', 1))
    payload = json.loads(raw)
    del payload["claim"]["received_at"]
    with pytest.raises(ValidationError):
        ClaimFixture.model_validate(payload)


def test_cors_allows_only_extension_origins():
    ext = "chrome-extension://" + "a" * 32
    allowed = client.get("/api/health", headers={"Origin": ext})
    assert allowed.headers["access-control-allow-origin"] == ext
    other = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", "Meridian demo"),
        ("/admin", "received → validated"),
        ("/claimspro/IS-CLM-2025004222", "Bodily Injury"),
        ("/panel?claim=IS-CLM-2025004222", "IS-CLM-2025004222"),
    ],
)
def test_pages_render(path, expected):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert expected in response.text


def test_claimspro_page_unknown_claim_is_404():
    assert client.get("/claimspro/IS-CLM-0000000000").status_code == 404


def test_basecoat_macros_render():
    from app import templates

    source = '{% from "components/tabs.html.jinja" import tabs %}{{ tabs(id="t", tabsets=[{"tab": "A", "panel": "x"}]) }}'
    html = templates.env.from_string(source).render()
    assert 'role="tablist"' in html


def test_pages_load_basecoat_before_app_css():
    html = client.get("/").text
    assert html.index("basecoat.cdn.min.css") < html.index("/static/app.css")
