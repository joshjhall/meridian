from pipeline.intake import check_correction, ocr_cross_check, validate

from fixtures import load_claim_fixtures

CLAIM_2993 = load_claim_fixtures()["IS-CLM-2025002993"].claim


def test_correction_that_drops_not_is_rejected_and_sent_to_a_person():
    raw = "n0t c0nsistent with a fresh impact"
    verdict = check_correction(raw, "consistent with a fresh impact")
    assert not verdict.accepted
    assert verdict.needs_person
    assert verdict.dropped == ["n0t"]
    assert verdict.reason == "negation changed"


def test_correction_that_adds_a_negation_is_rejected():
    verdict = check_correction("c0nsistent", "not consistent")
    assert not verdict.accepted and verdict.reason == "negation changed"


def test_character_only_correction_is_accepted():
    assert check_correction("n0t c0nsistent", "not consistent").accepted
    assert check_correction("CA-CA-88l23-l8", "CA-CA-88123-18").accepted


def test_word_swap_is_rejected_even_without_a_negation():
    verdict = check_correction("rear impact", "front impact")
    assert not verdict.accepted and verdict.reason == "words changed"


def test_2993_ocr_conflicts_are_proposals_not_changes():
    before = CLAIM_2993.model_dump()
    items = {i.label: i for i in ocr_cross_check(CLAIM_2993)}

    policy = items["Policy number"]
    assert policy.kind == "conflict"
    assert policy.values == ["fax: CA-CA-88l23-l8", "EDI: CA-CA-88123-18"]
    assert policy.suggested == "CA-CA-88123-18"

    bumper = items["Bumper cover rear line amount"]
    assert bumper.values[0] == "fax: 1,B00.00"
    assert bumper.suggested == "1,800.00"

    loss = items["Date of loss likely receipt date; unverified"]
    assert "EDI: 2025-09-08" in loss.values
    assert "estimate written 2025-09-05" in loss.values

    assert items["Claimant contact (phone chase)"].kind == "missing"
    assert CLAIM_2993.model_dump() == before


def test_claims_without_fax_sources_have_no_ocr_check():
    assert ocr_cross_check(load_claim_fixtures()["IS-CLM-2025000300"].claim) == []


def test_malformed_row_names_its_reasons():
    claim, issues = validate(
        {"claim_id": "bad", "filed_date": "2025-09-01", "claim_type": "Collision"}
    )
    assert claim is None
    assert any(i.startswith("claim_id:") for i in issues)
    assert any(i.startswith("state:") for i in issues)
