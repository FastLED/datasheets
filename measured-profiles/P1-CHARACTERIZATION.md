# P1 datasheet characterization — 2026-09-05

This is the reproducible P1 inventory for FastLED/FastLED#4035.  It is a
datasheet characterization report, not a calibration report.  The result is
intentionally conservative: no instrument-measured profile exists in this
commit, so P10 remains the external closure gate.

## Corpus and classification

`catalog-v1.json` inventories all 29 `addressable-led` part directories in
this checkout: 10 fixed-package integrated LED parts and 19 driver-only,
external-emitter parts.  Driver-only records must not acquire a chipset default
emitter profile; the P2 C8.5 fallback is required unless the fixture supplies
an artifact.  TM1829S is included despite having no PDF file, preventing a
silent coverage hole.

The checkout's PDFs are Git-LFS pointers and `git lfs` is unavailable. Source
URLs from `SOURCES.md` were fetched only into an untracked temporary directory:
nine of the ten integrated parts were retrievable and WS2816 returned HTTP 403.
The checked-in WS2812B artifact demonstrates page/table-scoped transcription.
No downloaded PDF is checked in or redistributed. The remaining catalog fields
are unknown until similarly transcribed with a corpus path, PDF page, section.

## What can and cannot be quantified now

No admitted artifact currently contains extracted CIE xy or a calibrated spectral
power distribution usable for xy/relative-Y conversion. This is not proof that
the corpus lacks usable spectra: SK9822 plots have not been digitized and the
WS2816 payload has not yet been inspected. A neutral,
primary, secondary, luminance, or ΔE2000 comparison requires each emitter's xy
and relative radiometric/photometric scale; a luminous-intensity RGB ratio
alone cannot establish ΔE2000.  Consequently there are **zero admissible
derived profiles**, no defensible clusters, and no numerical score for
`TypicalLEDStrip`, `Typical8mmPixel`, or `UncorrectedColor`.  Reporting zero
error or a five-part illustrative sample would falsely imply full-catalog
coverage. This is a quantified artifact-completeness result: 0/10 integrated
parts with admitted extracted spectral/xy data; 0/10 with a measured uncertainty;
0/10 currently usable for the A1 normalized ΔE calculation. P1 characterization
remains incomplete pending source extraction and the required numerical report.

When payload access is restored, calculate the three legacy models across
*every* admissible integrated record: use the profile full-drive white as
relative/adaptive white (Y=1, dark surround), test black-safe neutral ramp,
RGB primaries and CMY secondaries, record neutral chromaticity/Y error and
ΔE2000, then report count, median, p95 and excluded-part reasons.  Keep
datasheet-derived and instrument-measured rows separate.  Clustering is only
permitted after uncertainty/bins are present: report within-cluster versus
between-cluster variation and do not merge intervals that overlap at the
documented uncertainty.

## Schema and handoff

`SCHEMA.md` and `schema-v1.json` implement A2/C8 identity, append-only
provenance, B1 five-bit semantics, B10 reference-condition space, and strict
photometric/electrical separation.  P2 maps `chromaticity` to `Chromaticity`,
the channel set to `EmitterProfile`, response only when observed, and electrical
fields to its distinct electrical model.  The schema deliberately permits a
catalog record with incomplete photometry, but the generator must reject it as
`not_runtime_admissible`; missing evidence can never become a guessed profile.

## Measurement gate

P10 requires a checked-in report with a spectroradiometer (or an appropriately
spectrally corrected colorimeter), instrument identification, uncertainty,
fixed fixture geometry, drive conditions, temperature, bin/lot metadata, raw
data pointer, and the measured-profile validation set.  This commit supplies
the artifact shape and provenance enforcement only; it does not close that
gate.

## Extracted integrated-package inventory

This is an inventory of what the cited document says, not a calibrated-profile
claim. `—` means no usable table value; `I` is photopic luminous intensity
(mcd), not radiant or electrical power.

| Part / variant | source page | R/G/B wavelength nm | R/G/B I mcd | current / voltage | encoding / evidence gap |
| --- | ---: | --- | --- | --- | --- |
| APA102C | 1–3 | — | — | 22.5/24.5/26.5 mA output current at VDD=5 V | RGB8 + 5-bit current scale; no emitter/bin/thermal photometry |
| HD107 | 2–3 | — | — | 20 mA maximum, VDD 5.0 typical | RGB8 + 5-bit current scale, PWM >26 kHz; no emitter data |
| HD108 | 2–3 | — | — | 17 mA typical/20 mA max | RGB16 + per-channel 5-bit current scale, PWM 28 kHz; 0–70 °C only |
| SK6812 | 5 | 620–625 / 522.5–525 / 467.5–470 | 700–1000 / 1500–2200 / 700–1000 | V 2.0–2.2 / 3.0–3.3 / 3.0–3.3; current absent | RGB8 PWM; no bin/response curve |
| SK9822 | 4, 7 | graph only | graph only | 20 mA max, VDD 5.0 typical | RGB8 + 5-bit current scale; response/spectrum/thermal plots not digitized, no uncertainty |
| WS2812 | retrieved | — | — | — | RGB8 PWM; no extractable LED table |
| WS2812B | 3 | 620–625 / 522–525 / 465–467 | 390–420 / 660–720 / 180–200 | V 2.0–2.2 / 3.0–3.4 / 3.0–3.4; current absent | RGB8 PWM; no bin/response curve |
| WS2813 A/B/C/D | 5 | 620–622 / 522–525 / 467–470 | A 480/1500/320; B 360/1150/220; C 120/540/130; D 100/420/110 | 18/18/5/5 mA respectively | RGB8 PWM; variants, not a bin population |
| WS2815 | 3 | 620–625 / 515–525 / 465–475 | central 360/1150/220 | 15 mA/channel; 2.1 mA quiescent | RGB8 PWM; TA −20–70 °C but no thermal color curve/bin range |
| WS2816 | unavailable | — | — | primary source HTTP 403 | excluded pending primary access |

GS8208 is driver-only at the IC level, but its PDF page 8 gives an LED5050
package option at IF=10 mA (615–630/520–535/460–475 nm; 450/1300/280 mcd).
It is package-dependent, never a universal GS8208 default profile.

## Documented-intensity correction sensitivity (not color accuracy)

For rows with all three intensity values, each full-drive intensity is
multiplied by a legacy correction coefficient; the shown result is `max/min`
across R/G/B. Lower is a more even **photopic-intensity** neutral at that
condition, not chromaticity, flux, ΔE, a measurement, or a guarantee. Ranges
use their midpoint only for this calculation. Coefficients are from
`FastLED/src/color.h`: uncorrected `(1,1,1)`, strip `(1,176/255,240/255)`,
and 8 mm `(1,224/255,140/255)`.

| documented row | uncorrected | TypicalLEDStrip | Typical8mmPixel | ideal intensity-only inverse |
| --- | ---: | ---: | ---: | ---: |
| SK6812 midpoint | 2.18 | 1.60 | 3.48 | 1.00 |
| WS2812B midpoint | 3.63 | 2.66 | 5.81 | 1.00 |
| WS2813A | 4.69 | 3.44 | 7.50 | 1.00 |
| WS2813B / WS2815 central | 5.23 | 3.83 | 8.36 | 1.00 |
| WS2813C | 4.50 | 3.11 | 6.65 | 1.00 |
| WS2813D | 4.20 | 2.90 | 6.11 | 1.00 |
| GS8208 LED5050 option | 4.64 | 3.40 | 7.43 | 1.00 |

This covers 7 documented rows, not five cherry-picked rows. The spread rejects
a one-profile clustering conclusion: values vary by package/current/variant,
and PDFs supply no common bin population or uncertainty, so no quantitative
cluster confidence is defensible.
