# FastLED Datasheets — Agent Guide

This repository hosts vendor datasheets, reference manuals, errata, and
application notes for the silicon and LED chips FastLED targets. It is
**private** and intended as an internal reference for FastLED contributors
and agents.

## Layout rule (partition by vendor, then product type, then part number)

```
<vendor>/<product-type>/<part-number>/<file>
```

- **Vendor** — lowercase slug (`worldsemi`, `espressif`, `nxp`,
  `stmicroelectronics`, `nordic`, `raspberrypi`, `microchip`,
  `wch` for Nanjing Qinheng Microelectronics / WinChipHead,
  `siliconlabs`, `renesas`, `pjrc`, `arduino`, `gigadevice`, `ambiq`,
  `normand`, `apa`, `hdchips`, `titanmicro`, `newstar`, `sunmoon`,
  `ucs`, `genesisstar`). See the vendor table in `README.md`.
- **Product type** — `addressable-led`, `led-driver`, `soc`, `mcu`,
  `board`, `power`.
- **Part number** — uppercase, matching the vendor's part number
  (`WS2812B`, `SK6812`, `ESP32-S3`, `LPC845`, `RP2040`, …).

## Example paths agents should expect

- `worldsemi/addressable-led/WS2812B/datasheet.pdf`
- `worldsemi/addressable-led/SK6812/datasheet.pdf`
- `espressif/soc/ESP32-S3/technical-reference-manual.pdf`
- `espressif/soc/ESP32-C6/errata.pdf`
- `nxp/mcu/LPC845/user-manual.pdf`
- `raspberrypi/mcu/RP2040/datasheet.pdf`
- `wch/mcu/CH32V003/technical-reference-manual.pdf`

## Rules for agents

- **Do NOT copy PDFs into `FastLED/FastLED`.** Link to this repo by
  relative path from repo root instead.
- When you need a specific silicon detail (register offset, timing
  window, DMA constraint), the answer lives here in the corresponding
  vendor PDF — cite it by `<vendor>/<product-type>/<part-number>/<file>`
  plus page/section reference.
- When adding a new datasheet, follow the "Adding a new datasheet"
  procedure in `README.md`. Vendor and product-type slugs must come from
  the tables in `README.md` — do not invent new slugs without updating
  the tables in the same commit.
- This repo is **reference only**. No source code, no driver
  implementation notes (those belong in `FastLED/FastLED` under
  `agents/docs/`).

## Discoverability keywords

`datasheet`, `user manual`, `technical reference manual`, `errata`,
`worldsemi`, `WS2812`, `SK6812`, `APA102`, `espressif`, `ESP32`, `nxp`,
`LPC`, `RP2040`, `STM32`, `nRF52`, `teensy`, `vendor datasheet`,
`peripheral chapter`, `register map`.

## Cross-references

- `README.md` — full layout spec + vendor/product-type slug tables +
  contribution procedure.
- `FastLED/FastLED` `agents/docs/peripheral-existence.md` — the guardrail
  that requires citing a vendor datasheet chapter before writing driver
  code that assumes a peripheral exists on a chip. That guardrail should
  cite files from this repo.
- `FastLED/FastLED` `agents/docs/register-maps.md` — the CMSIS-first rule
  for register access. Vendor CMSIS PAL headers are one source of truth;
  the user manual PDFs stored here are the other.
