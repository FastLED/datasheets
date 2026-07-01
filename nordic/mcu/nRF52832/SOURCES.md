# nRF52832 sources

| Canonical file | Original filename / label | Source URL | Retrieved |
|---|---|---|---|
| `datasheet.pdf` | `4823_nRF52832_PS_v1.9.pdf` (nRF52832 Product Specification, v1.9) | https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/8881/4823_nRF52832_PS_v1.9.pdf | 2026-07-01 |
| `errata.pdf` | `nRF52832_Rev_2_Errata_v2.0.pdf` — nRF52832 Revision 2 Errata v2.0 | https://docs.nordicsemi.com/bundle/errata_nRF52832_Rev2/page/ERR/nRF52832/Rev2/latest/err_832.html (attachment `khub/maps/CqdMbiOw8pC~aCq~zcMRzQ`) | 2026-07-01 |

Notes:
- Official upstream is `docs.nordicsemi.com` / `infocenter.nordicsemi.com`, but
  those endpoints are gated by Cloudflare. Digi-Key hosts a verbatim copy of
  the PS.
- Errata upgraded from Rev 2 v1.0 (fukumi.blue mirror) to the current Rev 2
  v2.0. Fetched via Playwright due to Cloudflare/JS challenge — the docs
  SPA exposes the PDF via a `khub` attachment endpoint discovered from the
  errata bundle landing page. Direct `curl` and Playwright's
  `context.request` HTTP client both return 403.
- v1.9 is the latest publicly indexed Product Specification.
