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
VENDOR = BACKEND / "static" / "vendor"

# src/href values only: inline SVGs carry xmlns="http://www.w3.org/2000/svg",
# a namespace name the browser never fetches.
ASSET_URL = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""")
REMOTE = re.compile(r"^(?:https?:)?//(?!localhost\b|127\.0\.0\.1\b)", re.IGNORECASE)

PAGES = ["/admin", "/admin/queues", "/panel"]


def vendored_urls(html: str) -> list[str]:
    return [u for u in ASSET_URL.findall(html) if u.startswith("/static/vendor/")]


def test_no_template_references_a_remote_asset():
    remote = [
        f"{path.relative_to(TEMPLATES)}: {url}"
        for path in sorted(TEMPLATES.rglob("*.html*"))
        for url in ASSET_URL.findall(path.read_text())
        if REMOTE.match(url)
    ]
    assert remote == []


@pytest.mark.parametrize("page", PAGES)
def test_page_serves_every_vendored_asset_it_links(page):
    res = client.get(page)
    assert res.status_code == 200
    urls = vendored_urls(res.text)
    assert "/static/vendor/basecoat/basecoat.cdn.min.css" in urls
    assert "/static/vendor/htmx/htmx.min.js" in urls
    for url in urls:
        asset = client.get(url)
        assert asset.status_code == 200, url
        assert asset.content, url


def test_admin_loads_the_vendored_d3():
    assert "/static/vendor/d3/d3.min.js" in vendored_urls(client.get("/admin").text)


@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("htmx/htmx.min.js", 'version:"2.0.4"'),
        ("d3/d3.min.js", "d3js.org v7.9.0"),
    ],
)
def test_vendored_builds_are_the_pinned_versions(path, marker):
    assert marker in (VENDOR / path).read_text()


def test_vendor_readme_records_the_pinned_versions():
    readme = (VENDOR / "README.md").read_text()
    for pin in ("basecoat-css@1.0.2", "htmx.org@2.0.4", "d3@7.9.0"):
        assert pin in readme


@pytest.mark.parametrize("licence", ["basecoat/LICENSE.md", "htmx/LICENSE", "d3/LICENSE"])
def test_licences_ship_with_the_vendored_packages(licence):
    assert (VENDOR / licence).read_text().strip()


def test_d3_integrity_matches_the_local_file():
    template = (TEMPLATES / "admin" / "monitor.html").read_text()
    pinned = re.search(r'integrity="(sha384-[^"]+)"', template)
    assert pinned is not None
    digest = hashlib.sha384((VENDOR / "d3" / "d3.min.js").read_bytes()).digest()
    assert pinned.group(1) == "sha384-" + base64.b64encode(digest).decode()
