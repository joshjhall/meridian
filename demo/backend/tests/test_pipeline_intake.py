import pytest

from fixtures import load_claim_fixtures
from pipeline import intake
from pipeline.intake import check_correction, intake_gaps, ocr_cross_check, validate

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


def _swapped_claim(tmp_path, monkeypatch, *, ocr=None, edi=None):
    """Claim 2993 pointed at copies of its fax and EDI with the given {old: new} swaps."""
    src = intake.REPO / "sample_claims" / "IS-CLM-2025002993"
    for name, swaps in (("ocr_output.txt", ocr or {}), ("edi_record.txt", edi or {})):
        text = (src / name).read_text()
        for old, new in swaps.items():
            assert old in text, f"swap target not in {name}: {old!r}"
            text = text.replace(old, new)
        (tmp_path / name).write_text(text)
    monkeypatch.setattr(intake, "REPO", tmp_path)
    return CLAIM_2993.model_copy(update={"sources": ["ocr_output.txt", "edi_record.txt"]})


def _fax_claim(tmp_path, monkeypatch, *, edi_date: str, written: str):
    """Claim 2993 pointed at copies of its fax and EDI with the dates swapped out."""
    return _swapped_claim(
        tmp_path,
        monkeypatch,
        ocr={"2O25-O9-O5": written},
        edi={"DTP*439*D8*20250908": edi_date},
    )


def _items(claim) -> dict:
    """The cross-check's items by label, asserting nothing was applied to the claim."""
    before = claim.model_dump()
    items = {i.label: i for i in ocr_cross_check(claim)}
    assert claim.model_dump() == before
    return items


def test_unparsable_edi_date_becomes_an_attention_item(tmp_path, monkeypatch):
    claim = _fax_claim(tmp_path, monkeypatch, edi_date="DTP*439*D8*20251345", written="2O25-O9-O5")
    labels = [i.label for i in ocr_cross_check(claim)]
    assert "Date of loss unreadable; unverified" in labels


def test_impossible_ocr_estimate_date_becomes_an_attention_item(tmp_path, monkeypatch):
    claim = _fax_claim(tmp_path, monkeypatch, edi_date="DTP*439*D8*20250908", written="2O25-13-45")
    labels = [i.label for i in ocr_cross_check(claim)]
    assert "Date of loss unreadable; unverified" in labels


def test_short_dtp_segment_becomes_an_attention_item(tmp_path, monkeypatch):
    claim = _fax_claim(tmp_path, monkeypatch, edi_date="DTP*439*D8", written="2O25-O9-O5")
    labels = [i.label for i in ocr_cross_check(claim)]
    assert "Date of loss unreadable; unverified" in labels


def test_missing_or_escaping_source_raises_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "REPO", tmp_path)
    gone = CLAIM_2993.model_copy(update={"sources": ["ocr_output.txt", "edi_record.txt"]})
    with pytest.raises(intake.UnreadableSource, match="unreadable"):
        ocr_cross_check(gone)
    escaping = CLAIM_2993.model_copy(
        update={"sources": ["../etc/ocr_output.txt", "../etc/edi_record.txt"]}
    )
    with pytest.raises(intake.UnreadableSource, match="outside the repo"):
        ocr_cross_check(escaping)


def test_intake_gaps_lists_known_missing_documents():
    claim = load_claim_fixtures()["IS-CLM-2025002043"].claim
    gaps = intake_gaps(claim)
    assert [g.label for g in gaps] == claim.details["missing"]
    assert {g.kind for g in gaps} == {"missing"}


def _line_item(items: dict):
    return next((i for label, i in items.items() if label.endswith(" line amount")), None)


INSURED = "NM1*IL*2*PACIFIC FREIGHT PARTNERS INC*****MI*CA-CA-88123-18~"
CLAIMANT = "NM1*QC*1*MENDEZ*GLORIA****MI*CLMT-2025002993~"


def test_matching_policy_number_raises_nothing(tmp_path, monkeypatch):
    claim = _swapped_claim(tmp_path, monkeypatch, ocr={"CA-CA-88l23-l8": "CA-CA-88123-18"})
    assert "Policy number" not in _items(claim)


@pytest.mark.parametrize(
    "insured",
    [
        pytest.param("NM1*IL*2*PACIFIC FREIGHT PARTNERS INC~", id="short"),
        pytest.param("", id="missing"),
    ],
)
def test_short_or_missing_insured_segment_raises_no_policy_item(tmp_path, monkeypatch, insured):
    claim = _swapped_claim(tmp_path, monkeypatch, edi={INSURED: insured})
    assert "Policy number" not in _items(claim)


def test_unreadable_line_is_solved_against_the_recap_total(tmp_path, monkeypatch):
    claim = _swapped_claim(tmp_path, monkeypatch, ocr={"Parts 2,728.5O": "Parts 2,828.5O"})
    item = _line_item(_items(claim))
    assert item is not None and item.kind == "conflict"
    assert item.values == [
        "fax: 1,B00.00",
        "line items sum to the recap parts total only at 1,900.00",
    ]


def test_readable_lines_that_miss_the_recap_total_raise_nothing(tmp_path, monkeypatch):
    # Pins current behavior: the check only solves for exactly one unreadable line, so a
    # fully readable estimate that doesn't sum to the recap goes unflagged. See #56.
    claim = _swapped_claim(tmp_path, monkeypatch, ocr={"1,B00.00": "1,700.00"})
    assert _line_item(_items(claim)) is None


@pytest.mark.parametrize(
    "swap",
    [
        pytest.param({"R&R 64O.OO": "R&R 6B0.00"}, id="two-unreadable-amounts"),
        pytest.param({"p.6 recap": "p.6 summary"}, id="no-recap"),
        pytest.param({"p.3 line items": "p.3 lines"}, id="no-line-items"),
    ],
)
def test_line_items_without_a_single_solvable_line_raise_nothing(tmp_path, monkeypatch, swap):
    claim = _swapped_claim(tmp_path, monkeypatch, ocr=swap)
    assert _line_item(_items(claim)) is None


@pytest.mark.parametrize(
    ("ocr", "edi"),
    [
        pytest.param({"C0NTACT ____________": "C0NTACT (909) 555-0199"}, {}, id="on-fax"),
        pytest.param(
            {}, {CLAIMANT: CLAIMANT + "\nPER*IC*GLORIA MENDEZ*TE*9095550199~"}, id="in-edi"
        ),
    ],
)
def test_claimant_contact_present_raises_nothing(tmp_path, monkeypatch, ocr, edi):
    claim = _swapped_claim(tmp_path, monkeypatch, ocr=ocr, edi=edi)
    assert "Claimant contact (phone chase)" not in _items(claim)


@pytest.mark.parametrize(
    "claimant",
    [
        pytest.param(CLAIMANT + "\nPER~", id="bare-per"),
        pytest.param(CLAIMANT + "\nPER*~", id="empty-per"),
        pytest.param("", id="no-claimant-nm1"),
    ],
)
def test_short_or_missing_claimant_contact_is_chased(tmp_path, monkeypatch, claimant):
    claim = _swapped_claim(tmp_path, monkeypatch, edi={CLAIMANT: claimant})
    assert _items(claim)["Claimant contact (phone chase)"].kind == "missing"
