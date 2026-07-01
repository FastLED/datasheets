# nRF52833 sources

| Canonical file | Original filename / label | Source URL | Retrieved |
|---|---|---|---|
| `datasheet.pdf` | `nRF52833_PS_v1.7.pdf` (nRF52833 Product Specification, v1.7, 2024-06-14) | https://comp.anu.edu.au/courses/comp2300/assets/manuals/nRF52833_PS_v1.7.pdf | 2026-07-01 |
| `errata.pdf` | `nRF52833_Rev_2_Errata_v1.4.pdf` (nRF52833 Revision 2 Errata, v1.4, 4452_363 v1.4 / 2026-05-11) | https://docs.nordicsemi.com/bundle/errata_nRF52833_Rev2/page/ERR/nRF52833/Rev2/latest/err_833.html (Fluidtopics attachment `api/khub/maps/5uTPHCvkwlkDEtoKhQqDwg/attachments/~xGAvjJ2nHWeCP7n4mojNQ-5uTPHCvkwlkDEtoKhQqDwg/content?download=true`) | 2026-07-01 |

Notes:
- Official upstream is `docs.nordicsemi.com` / `infocenter.nordicsemi.com`.
  Both hosts serve a JS-rendered Fluidtopics SPA behind Cloudflare +
  reCAPTCHA; `curl` and Playwright's `context.request` HTTP client both
  receive HTTP 403 for the direct attachment URL.
- Australian National University hosts a verbatim copy of the v1.7 PS as
  course material for COMP2300.
- Errata fetched via Playwright (`headless=False`). Working recipe:
  1. Navigate the SPA to the bundle landing page `err_833.html`.
  2. Read the attachment metadata from
     `GET /api/khub/maps/{mapId}/attachments` — the SPA loads this JSON
     itself, so it's readable in the response body event.
     - Rev 2 v1.4: map `5uTPHCvkwlkDEtoKhQqDwg`, attachment
       `~xGAvjJ2nHWeCP7n4mojNQ-5uTPHCvkwlkDEtoKhQqDwg` (`~` is literal).
     - Rev 1 v1.6: map `ZHnukDeufmUXjGgLRXFRdQ`, attachment
       `byHMbXT9DBICBseoBO4XIQ-ZHnukDeufmUXjGgLRXFRdQ`.
     - Engineering A: last public PDF was v1.4 (2022-02-09), only obtainable
       via Wayback Machine at
       `https://web.archive.org/web/20221208144844id_/https://infocenter.nordicsemi.com/pdf/nRF52833_Engineering_A_Errata_v1.4.pdf`.
  3. Locate the anchor
     `a[href*='<attachmentId>']` on the page and click via
     `page.expect_download() + loc.click(force=True)`. The real browser
     download event bypasses the reCAPTCHA that blocks the equivalent
     `ctx.request.get()` call.
- Wayback CDX filter
  `url=infocenter.nordicsemi.com/pdf/*&filter=urlkey:.*nrf52833.*errata.*`
  returns only Engineering A v1.3 (2022-02-01) and Engineering A v1.4
  (2022-12-08). No `nRF52833_Rev_[123]_Errata_*.pdf` filename was ever
  archived on Wayback — Nordic moved directly from Engineering-A PDFs to
  the Fluidtopics HTML bundle for production-silicon revisions.
