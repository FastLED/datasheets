# TM1829S — no separate datasheet

**Verdict (verified 2026-07-01):** TM1829S is **not** a distinct part
number in Titan Micro Electronics' catalog. It appears to be a
board-house / distributor-invented suffix (or a typo of "TM1829 SOP-8")
that shares the base TM1829 spec sheet.

## Use the base TM1829 datasheet

- [`../TM1829/datasheet.pdf`](../TM1829/datasheet.pdf) — Titan Micro
  Electronics TM1829 V1.4 (English translation of the Chinese original
  `TM1829_V1.4-chin.pdf`, dated 2013-12-07 by BNT).

## Evidence that TM1829S is not a separate product

1. **Titan Micro official datasheet (V1.4, page 1)** lists only two
   package options for the base part: `Package: SOP8, DIP8`. No "S"
   suffix or subvariant is defined anywhere in the 15-page document.
   Package drawings on pages 12–14 show `SOP8` and `DIP8` only. No
   ordering-code table exists that would introduce a TM1829S SKU.

2. **Advatek Lighting's pixel-protocol registry**
   (https://www.advateklighting.com/pixel-protocols/tm1829) — the
   authoritative third-party protocol catalog for addressable pixel ICs
   — lists **only "TM1829"** in SOP8. No `TM1829S`, `TM1829-S`, or any
   sub-variant is registered.

3. **LCSC (Titan Micro's primary distributor)** — the product page for
   `C5174518` lists only TM1829 (SOP-8, DIP-8). No `TM1829S` SKU exists
   in LCSC's catalog. The 2024-10-12 datasheet (`lcsc_datasheet_
   2410121248_TM-Shenzhen-Titan-Micro-Elec-TM1829_C5174518.pdf`) is
   the same V1.4 spec.

4. **Web search sweeps** for `"TM1829S" filetype:pdf`,
   `TM1829S datasheet`, `TM1829S 天微 数据手册`, and Chinese electronics
   forums returned **zero** results referencing TM1829S as a distinct
   part — every hit was for the base TM1829. The only sibling actually
   catalogued by Titan Micro is **TM1929** (a different part number, not
   a TM1829 variant).

## Implication for FastLED

TM1829S strips / modules should be treated as TM1829 for driver
purposes:

- Single-wire cascaded protocol, ~800 Kbps low-speed / 1.6 Mbps
  high-speed (base datasheet page 1).
- 3 channels, 8-bit PWM per channel, 5-bit / 32-step constant-current
  control (10–41 mA range).
- Power: OUT rated 24V, VDD 5V regulator with series-resistor input
  6–24V.
- Package: SOP8 or DIP8 only.

If a vendor sells a strip labelled "TM1829S", the physical IC inside is
almost certainly a standard TM1829 in SOP8 — the trailing "S" typically
denotes the SOP packaging in board-house shorthand, not a separate
silicon revision.

## What would change this verdict

If a datasheet PDF surfaces that:

- carries the Titan Micro (`www.titanmec.com`) footer,
- names "TM1829S" in the title (not just as a family aside), and
- shows electrical specs that differ from TM1829 (e.g. different pin
  count, different protocol timing, different constant-current range),

then treat TM1829S as a distinct part, save the PDF to
`titanmicro/addressable-led/TM1829S/datasheet.pdf`, delete this
`README.md`, and update FastLED bus tables accordingly. Until then, this
directory exists purely as a discoverability tombstone so future agents
don't repeat the hunt.
