# nRF52840 sources

| Canonical file | Original filename / label | Source URL | Retrieved |
|---|---|---|---|
| `datasheet.pdf` | `NRF52840-DK.pdf` — nRF52840 Product Specification v1.11 (4413_417 v1.11 / 2024-10-01) | https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6469/NRF52840-DK.pdf | 2026-07-01 |
| `errata.pdf` | `nRF52840_Rev_3_Errata_v1.4.pdf` — nRF52840 Revision 3 Errata v1.4 | https://docs.nordicsemi.com/bundle/errata_nRF52840_Rev3/page/ERR/nRF52840/Rev3/latest/err_840.html (attachment `khub/maps/BXkfxmdfBx5JJ9pQdp2FLQ`) | 2026-07-01 |

Notes:
- Official upstream is `docs.nordicsemi.com` / `infocenter.nordicsemi.com`,
  gated by Cloudflare. The errata was fetched via a Playwright-driven
  Chromium session that Cloudflare accepted; direct `curl` and Playwright's
  `context.request` HTTP client both return 403. The docs SPA exposes the
  PDF via a `khub` attachment endpoint discovered from the errata bundle
  landing page.
- Digi-Key hosts a verbatim copy of PS v1.11 (latest as of 2024-10-01).
- Errata upgraded from Engineering A v1.0 (2016 pre-production) to Rev 3
  v1.4 — matches current production silicon.
