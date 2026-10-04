import csv
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import app
from fixtures import DATA, load_history
from models import LearningHistory

REPO = DATA.parents[1]
client = TestClient(app)


def charts():
    return {c.id: c for c in load_history().charts}


def test_history_loads_and_api_serves_it():
    history = load_history()
    assert {c.id for c in history.charts} == {"routing", "intake"}
    res = client.get("/api/history")
    assert res.status_code == 200
    assert LearningHistory.model_validate(res.json()) == history


def test_series_share_one_week_axis():
    weeks = {
        tuple(p.week for p in s.points)
        for c in load_history().charts
        for s in (c.primary, c.secondary)
    }
    assert len(weeks) == 1
    (axis,) = weeks
    assert axis == tuple(range(len(axis)))


def test_routing_agreement_starts_at_calibration_flag_agreement():
    # analysis/review_floor.py section 4: current flag vs review_actually_needed.
    with (REPO / "reference" / "claims_processing.csv").open(newline="") as f:
        cal = [r for r in csv.DictReader(f) if r["review_actually_needed"]]
    agree = sum(r["flagged_for_human_review"] == r["review_actually_needed"] for r in cal)
    expected = round(100 * agree / len(cal), 1)
    assert expected == 76.0
    assert charts()["routing"].primary.points[0].value == expected


def test_other_series_start_at_cited_values():
    routing, intake = charts()["routing"], charts()["intake"]
    assert routing.secondary.points[0].value == 68  # docs/project/sow.md:17
    sow = (REPO / "docs" / "project" / "sow.md").read_text()
    assert "68h average" in sow
    # memory/calltranscripts/w1-thu-michael-systems.md:143: ~78% OCR, 1 in 8 EDI dropped.
    transcript = (REPO / "memory" / "calltranscripts" / "w1-thu-michael-systems.md").read_text()
    assert "seventy-eight percent" in transcript
    assert "one partner submission in eight" in transcript
    assert intake.primary.points[0].value == 78
    assert abs(intake.secondary.points[0].value - 100 / 8) < 0.5


def test_series_end_at_their_targets():
    for chart in load_history().charts:
        for s in (chart.primary, chart.secondary):
            assert s.points[-1].value == s.target, s.key


def test_one_release_regresses_and_is_rolled_back():
    history = load_history()
    rollbacks = [r for r in history.releases if r.kind == "rollback"]
    assert len(rollbacks) == 1
    rollback = rollbacks[0]
    before = max(
        (r for r in history.releases if r.kind == "release" and r.week < rollback.week),
        key=lambda r: r.week,
    )
    assert before.version.split()[0] == rollback.version.split()[0]
    assert before.week >= 1
    agreement = charts()["routing"].primary.points
    assert agreement[before.week].value < agreement[before.week - 1].value
    assert agreement[rollback.week].value > agreement[before.week].value


def test_releases_name_known_charts_and_have_notes():
    ids = set(charts())
    last_week = charts()["routing"].primary.points[-1].week
    for r in load_history().releases:
        assert r.charts and set(r.charts) <= ids
        assert r.notes
        assert 0 <= r.week <= last_week, r.version
    versions = {r.version for r in load_history().releases}
    assert {
        "router v0.3",
        "ocr-check v1.1",
        "signals-prompt v1.2",
        "signals-prompt v1.3",
    } <= versions


def test_caption_marks_history_illustrative_and_one_axis_per_plot():
    caption = load_history().caption
    assert "Illustrative" in caption
    assert "targets" in caption
    assert "own plot and y-axis" in caption


def test_monitor_leaves_learning_charts_to_their_own_page():
    # Live card moves repainted under the charts, so they moved off /admin.
    html = client.get("/admin").text
    assert 'id="learning-loop"' not in html
    assert "/static/learning.js" not in html
    assert 'href="/admin/learning?view=admin"' in html


def test_learning_page_includes_learning_charts():
    res = client.get("/admin/learning")
    assert res.status_code == 200
    html = res.text
    assert 'id="learning-loop"' in html
    assert "Illustrative history" in html
    assert "/static/learning.js" in html
    # D3 is vendored (#55) and still pinned with Subresource Integrity.
    d3_tag = re.search(r'<script[^>]*src="/static/vendor/d3/d3\.min\.js"[^>]*>', html)
    assert d3_tag
    assert re.search(r'integrity="sha384-[A-Za-z0-9+/=]+"', d3_tag.group())
    assert 'data-chart="routing"' in html
    assert 'data-chart="intake"' in html
    # Four single-axis plots: each box splits its two series into two panels.
    assert html.count('data-role="plot"') == 4
    assert html.count('data-series="primary"') == html.count('data-series="secondary"') == 2


@pytest.mark.parametrize(
    ("path", "bad"),
    [(("releases", 0, "kind"), "hotfix"), (("charts", 0, "primary", "mark"), "area")],
)
def test_schema_rejects_unknown_kind_and_mark(path, bad):
    data = load_history().model_dump()
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = bad
    with pytest.raises(ValidationError):
        LearningHistory.model_validate(data)


def test_learning_js_never_writes_html():
    # Release notes and labels come from the API; the script must set text only.
    js = (DATA.parent / "backend" / "static" / "learning.js").read_text()
    # Comments may name the APIs they avoid; strip only whole-line comments so a
    # "//" inside a string (a URL) can't hide code after it.
    code = re.sub(r"(?m)^\s*//[^\n]*", "", js)
    for sink in (
        r"(inner|outer)HTML",
        r"insertAdjacentHTML",
        r"document\.write",
        r"DOMParser",
        r"createContextualFragment",
        r"\.html\(",
        r"setAttribute\(\s*[\"']on",
    ):
        assert not re.search(sink, code), sink
