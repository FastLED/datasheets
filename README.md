# FastLED Datasheets

Central store for vendor datasheets, reference manuals, errata, and product
briefs for the silicon and LED chips that FastLED targets.

> **Access:** private — internal reference material. Redistribution of any
> individual PDF is governed by the original vendor's copyright and license
> terms. This repo curates and organizes references; it does not relicense.

## Layout

Content is partitioned first by **vendor**, then by **product type**, then
by **part number**:

```
<vendor>/<product-type>/<part-number>/<file>
```

Vendor directories are lowercase, dash-separated where needed
(`world-semi` is written `worldsemi`, not `WorldSemi`). Product-type
directories are lowercase and describe the *category* the vendor sells,
not the FastLED driver name. Part-number directories match the part
number as printed on the die/package (uppercase, e.g. `WS2812B`,
`ESP32-S3`).

### Example tree

```
worldsemi/
  addressable-led/
    WS2811/
      datasheet.pdf
      timing-notes.md
    WS2812B/
      datasheet.pdf
    WS2815/
    SK6812/
espressif/
  soc/
    ESP32/
      technical-reference-manual.pdf
      datasheet.pdf
      errata.pdf
    ESP32-S3/
    ESP32-C6/
    ESP32-P4/
nxp/
  mcu/
    LPC845/
      user-manual.pdf
      datasheet.pdf
    LPC804/
      user-manual.pdf
      datasheet.pdf
stmicroelectronics/
  mcu/
    STM32F411/
    STM32H750/
nordic/
  mcu/
    nRF52840/
raspberrypi/
  mcu/
    RP2040/
      datasheet.pdf
    RP2350/
pjrc/
  board/
    teensy-4.1/
```

### Vendor slug conventions (extend as new silicon is added)

| Vendor slug | Real vendor |
|---|---|
| `worldsemi` | World Semi (WS28xx, WS2801) |
| `espressif` | Espressif Systems (ESP32 family, ESP8266) |
| `nxp` | NXP Semiconductors (LPC, Kinetis K/KL, i.MX RT) |
| `stmicroelectronics` | STMicroelectronics (STM32) |
| `nordic` | Nordic Semiconductor (nRF51/nRF52) |
| `raspberrypi` | Raspberry Pi Ltd (RP2040, RP2350) |
| `microchip` | Microchip / Atmel (AVR ATmega/ATtiny, SAMD, SAM3X) |
| `siliconlabs` | Silicon Labs (EFR32MG24, MGM240) |
| `renesas` | Renesas Electronics (RA4M1, RA6M5) |
| `pjrc` | PJRC (Teensy) |
| `arduino` | Arduino (SA / LLC — boards published under Arduino's own SKU, e.g. UNO Q) |
| `gigadevice` | GigaDevice |
| `ambiq` | Ambiq Micro (Apollo3 Blue and other ultra-low-power Cortex-M4F MCUs) |
| `normand` | Shenzhen Normand Electronic (SK6812, SK9822, SK6805) |
| `apa` | APA Electronic / iPixel LED Light (APA102, APA102C) |
| `hdchips` | Chongqing HD Semiconductor (HD107, HD108) |
| `titanmicro` | Titan Micro Electronics (TM series LED ICs, LPD8806, LPD6803 — original silicon vendor is ambiguous for LPD parts) |
| `newstar` | Shiji Lighting / Newstar (P9813 — datasheet attributes DMS Microelectronics; community convention is Newstar) |
| `sunmoon` | Shenzhen Sunmoon Micro (SM16716, SM16703) |
| `ucs` | UltraChip (UCS1903, UCS2903, UCS7604, UCS8903) |
| `genesisstar` | Genesis Star (GS8208) |

### Product-type slugs

| Slug | Meaning |
|---|---|
| `addressable-led` | Serial-addressable LED ICs (WS28xx, SK6812, APA102, LPD8806, etc.) |
| `led-driver` | Non-addressable LED driver ICs (TLC59xx, PCA9685, etc.) |
| `soc` | System-on-chip with integrated peripherals (ESP32 family) |
| `mcu` | Microcontroller units without integrated Wi-Fi/BT |
| `board` | Full board reference (Teensy, dev kits) |
| `power` | Regulators, LDOs, buck converters |

### File naming

Prefer the vendor's own filename when unambiguous. If renaming for
consistency, use one of:

- `datasheet.pdf`
- `user-manual.pdf`
- `technical-reference-manual.pdf`
- `errata.pdf`
- `product-brief.pdf`
- `application-note-<topic>.pdf`

For extracted / OCR'd text alongside a PDF, use the same base name with
`.txt` or `.md` suffix (`datasheet.pdf` + `datasheet.txt`).

## What to put here

- Official vendor PDFs (datasheet, user manual / technical reference,
  errata, product briefs).
- Application notes that describe silicon behavior FastLED depends on
  (peripheral timings, DMA constraints, LED protocol waveforms).
- Timing / register annotations that supplement a PDF — put these in
  Markdown next to the PDF.

## What NOT to put here

- FastLED source code (belongs in `FastLED/FastLED`).
- Driver implementation notes (belongs in `agents/docs/` in the main repo).
- Anything under an NDA — this repo is private but not zero-trust; assume
  every collaborator on the FastLED org can read it.

## Referencing from the main repo

FastLED source and agent docs may link to a specific file by relative
path from repo root, e.g.:

- `worldsemi/addressable-led/WS2812B/datasheet.pdf`
- `nxp/mcu/LPC845/user-manual.pdf#page=214` (page anchors are supported by
  most PDF renderers when the file is served through the GitHub UI).

Do NOT copy PDFs into the main repo. Link to them here instead.

## Adding a new datasheet

1. Identify the vendor slug (from the table above; add a new row if it is
   a new vendor).
2. Identify the product-type slug.
3. Create `<vendor>/<product-type>/<part-number>/` if it does not already
   exist.
4. Drop the PDF in with a canonical filename (see "File naming" above).
5. If you renamed the file from what the vendor ships, record the
   original filename + source URL in a `SOURCES.md` next to it.
6. Commit with a message of the form
   `add <vendor>/<product-type>/<part-number>/<file>`.

## Companion doc

`CLAUDE.md` in this repo restates the layout in the form agents load
automatically. Update both files together when the layout changes.
