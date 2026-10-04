"""Self-hosted front-end assets (#55): no page loads anything from a third-party host."""

import base64
import hashlib
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

BACKEND = Path(__file__).parents[1]
TEMPLATES = BACKEND / "templates"
STATIC = BACKEND / "static"
VENDOR = STATIC / "vendor"

ASSET_URL = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""")
REMOTE = re.compile(r"^(?:https?:)?//(?!localhost\b|127\.0\.0\.1\b)", re.IGNORECASE)
# Our own CSS/JS: url()/@import targets and quoted string literals. Comments
# (e.g. the Tailwind licence banner in app.css) are not fetched.
STATIC_URL = re.compile(
    r"""url\(\s*["']?([^"')\s]+)|@import\s+["']([^"']+)|["'`]((?:https?:)?//[^"'`]+)"""
)
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
ABSOLUTE_URL = re.compile(r"""https?://(?!localhost\b|127\.0\.0\.1\b)[^\s"'`<>)]+""", re.IGNORECASE)
# Namespace names in inline SVG are identifiers, never fetched.
XML_NAMESPACES = {"http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"}

# Upstream builds, byte-for-byte; digests recorded in static/vendor/README.md.
VENDORED = {
    "basecoat/basecoat.cdn.min.css": (
        "XWKdrxzE2X33lI8Q03C9fIbqdLWV11whVNycR2/3bMNJY73EEQOa7rmN+SeiSCor"
    ),
    "basecoat/all.min.js": "rD2ZCuReXV7nIneJcn1lsTn6yOv87YARLQyUsemVAxrYYHdy5hcAW8XZEQxx87Dj",
    "htmx/htmx.min.js": "HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+",
    "d3/d3.min.js": "CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i",
}

PAGES = ["/admin", "/admin/learning", "/admin/queues", "/panel"]


def sha384(path: Path) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()


def vendored_urls(html: str) -> list[str]:
    return [u for u in ASSET_URL.findall(html) if u.startswith("/static/vendor/")]


def test_no_template_references_a_remote_asset():
    remote = []
    for path in sorted(TEMPLATES.rglob("*.html*")):
        text = path.read_text(encoding="utf-8")
        # Protocol-relative //host URLs in attributes, plus any absolute URL
        # anywhere: inline <style>/<script>, srcset, hx-get and the like.
        urls = [u for u in ASSET_URL.findall(text) if u.startswith("//") and REMOTE.match(u)]
        urls += [u for u in ABSOLUTE_URL.findall(text) if u not in XML_NAMESPACES]
        remote += [f"{path.relative_to(TEMPLATES)}: {url}" for url in urls]
    assert remote == []


def test_no_own_static_file_references_a_remote_asset():
    own = [
        p
        for p in sorted(STATIC.rglob("*"))
        if p.suffix in {".css", ".js"} and VENDOR not in p.parents
    ]
    assert own
    remote = [
        f"{path.relative_to(STATIC)}: {url}"
        for path in own
        for match in STATIC_URL.findall(COMMENT.sub("", path.read_text(encoding="utf-8")))
        for url in match
        if url and REMOTE.match(url) and "www.w3.org/2000/svg" not in url
    ]
    assert remote == []


@pytest.mark.parametrize("page", PAGES)
def test_page_serves_every_vendored_asset_it_links(page):
    res = client.get(page)
    assert res.status_code == 200
    urls = vendored_urls(res.text)
    for required in ("basecoat/basecoat.cdn.min.css", "basecoat/all.min.js", "htmx/htmx.min.js"):
        assert f"/static/vendor/{required}" in urls
    for url in urls:
        asset = client.get(url)
        assert asset.status_code == 200, url
        assert asset.content, url


def test_learning_page_loads_the_vendored_d3():
    assert "/static/vendor/d3/d3.min.js" in vendored_urls(client.get("/admin/learning").text)


@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("htmx/htmx.min.js", 'version:"2.0.4"'),
        ("d3/d3.min.js", "d3js.org v7.9.0"),
    ],
)
def test_vendored_builds_are_the_pinned_versions(path, marker):
    assert marker in (VENDOR / path).read_text(encoding="utf-8")


@pytest.mark.parametrize(("path", "digest"), VENDORED.items())
def test_vendored_files_match_their_recorded_digests(path, digest):
    assert sha384(VENDOR / path) == f"sha384-{digest}"
    assert f"sha384-{digest}" in (VENDOR / "README.md").read_text(encoding="utf-8")


def test_vendor_readme_records_the_pinned_versions():
    readme = (VENDOR / "README.md").read_text(encoding="utf-8")
    for pin in ("basecoat-css@1.0.2", "htmx.org@2.0.4", "d3@7.9.0"):
        assert pin in readme


@pytest.mark.parametrize("licence", ["basecoat/LICENSE.md", "htmx/LICENSE", "d3/LICENSE"])
def test_licences_ship_with_the_vendored_packages(licence):
    assert (VENDOR / licence).read_text(encoding="utf-8").strip()


def test_d3_integrity_matches_the_local_file():
    template = (TEMPLATES / "admin" / "learning.html").read_text(encoding="utf-8")
    pinned = re.search(r'integrity="(sha384-[^"]+)"', template)
    assert pinned is not None
    assert pinned.group(1) == sha384(VENDOR / "d3" / "d3.min.js")


@pytest.mark.parametrize(
    ("page", "own"),
    [("/admin", "admin.js"), ("/admin/learning", "learning.js"), ("/admin/queues", "queues.js")],
)
def test_own_scripts_carry_a_version_so_browsers_refetch_changes(page, own):
    # StaticFiles sends no Cache-Control, so a stale cached script kept running
    # after a fix; the ?v= stamp gives every change a new URL.
    html = client.get(page).text
    assert re.search(rf'src="/static/{re.escape(own)}\?v=\d+"', html)
    assert re.search(r'href="/static/app\.css\?v=\d+"', html)
