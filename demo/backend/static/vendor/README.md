# Vendored front-end libraries

Self-hosted copies of the libraries the demo pages load, so the demo runs with no network (#55). Each file is byte-for-byte the published npm build at the pinned version, fetched from jsDelivr. Do not edit them; to upgrade, replace the file from the new version's URL and update this table.

| File | Package | Version | Source | Licence |
| --- | --- | --- | --- | --- |
| `basecoat/basecoat.cdn.min.css` | basecoat-css | 1.0.2 | <https://cdn.jsdelivr.net/npm/basecoat-css@1.0.2/dist/basecoat.cdn.min.css> | MIT, `basecoat/LICENSE.md` |
| `basecoat/all.min.js` | basecoat-css | 1.0.2 | <https://cdn.jsdelivr.net/npm/basecoat-css@1.0.2/dist/js/all.min.js> | MIT, `basecoat/LICENSE.md` |
| `htmx/htmx.min.js` | htmx.org | 2.0.4 | <https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js> | 0BSD, `htmx/LICENSE` |
| `d3/d3.min.js` | d3 | 7.9.0 | <https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js> | ISC, `d3/LICENSE` |

`admin/monitor.html` keeps a Subresource Integrity hash on `d3.min.js`; `tests/test_assets.py` checks it still matches the local file.
