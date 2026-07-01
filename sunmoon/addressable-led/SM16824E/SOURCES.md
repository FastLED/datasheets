# SM16824E datasheet

- Original filename: `SM16824E明微产品说明书.pdf`
  (stored as `2-2312041HP44W.pdf` on the vendor CDN)
- Source URL: https://www.linkage.cn/uploads/allimg/20231204/2-2312041HP44W.pdf
- Vendor page: https://www.linkage.cn/quancai/ (product-family index — 幻彩/all-color LED driver ICs)
- Retrieved: 2026-07-01
- Vendor: Shenzhen Zhengmingke Electronics Co., Ltd. (深圳市钲铭科电子有限公司,
  English brand "Linkage"). Historically the die is co-branded / re-marketed
  as Shenzhen Sunmoon Micro ("Mingwei" / 明微), which is why JLCPCB lists the
  part as `Shenzhen Sunmoon Micro SM16824E` (JLCPCB code `C5173616`).
- Revision: IBZOZOV1.2 — SM16824E 景观装饰驱动 IC (landscape / decorative
  lighting driver, 13 pages, Chinese with pin diagrams).
- Highlights: single-wire clockless four-channel (R/G/B/W) constant-current
  driver, 60–350 mA per channel via REXT, 65536-level PWM grayscale
  (GAMMA-corrected), 4 kHz refresh (SM-PWM), 800 kbps single-polarity
  return-to-zero encoding, cascade data reshaping, SOP-8 (ESOP-8) package.
- Notes:
  - `www.scribd.com/document/757938003/SM16824E-zh-CN-en-1` is the same
    document (with an added English translation column) but is login-walled
    on scribd — not usable per the "do NOT attempt Scribd login" rule.
  - Referenced by FastLED issue #1941 ("Support for SM16824E and SM167035P3")
    where the timings T0H/T0L/T1H/T1L = 0.3 / 0.9 / 0.9 / 0.3 µs came from
    this same datasheet.
