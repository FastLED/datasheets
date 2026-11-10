# WS2812B V6 / V7 current consumption

Vendor clarification supplied with the V6 and V7 datasheets
(`WS2812B-V6_EN.pdf`, `WS2812B-V7_EN.pdf`) on 2026-11-09. It corrects a common
modelling error: the sub-microamp figure is an **idle** number and must not be
used to estimate draw while the part is being driven.

| Condition | Current |
|---|---|
| No data signal (quiescent / idle) | **< 1 µA** |
| During data transmission (IC operating current) | **≈ 150 µA** |

Quoting the vendor: the "< 1 µA" specification *"applies to the idle state
without data transmission and should not be used directly to estimate
consumption during"* transmission.

## Why it matters for a power model

These figures are the **IC's own** supply current — they exclude the LED dice,
which dominate total draw and are set by PWM brightness, not by this number.
Treat 150 µA as the per-pixel logic overhead to add on top of the LED current
when a frame is being clocked out, and 1 µA only when the bus is idle. Using
1 µA as the active figure understates the chip's contribution by roughly 150×.

## Brightness difference between the revisions

The vendor also states that **V7 delivers three times the brightness of V6**.
That is a property of the rev, not a datasheet typo: two boards that look
identical can differ by 3× in luminous output depending on which silicon they
carry, so record the revision when comparing measurements.

## Provenance limit

The figures above are from the vendor's email of 2026-11-09 and are reproduced
here as a supplement to the PDFs; where the PDFs disagree, the PDFs win. Neither
number was measured by FastLED.
