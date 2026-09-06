# Emitter profile artifact schema, v1

This directory is the append-only calibration-artifact registry selected by
FastLED/FastLED#4033 A2 and C8.  It contains machine-readable artifacts, not
firmware code.  Firmware never parses these files; a later reviewed generator
is the only bridge to generated C++.

## Identity and compatibility

Every artifact has `schema_version: "1.0"` and a canonical `profile_id`:

```
<part>/<package_variant>/<w_channel_variant>/<report_id>
```

Segments are lowercase ASCII `[a-z0-9][a-z0-9._-]*`; `w_channel_variant` is
`none` for RGB devices.  `identity` repeats the four components so tooling
does not need to parse IDs.  A production bin/lot is provenance metadata,
never identity.  Once published an ID and its JSON bytes are immutable.  A
correction or a new measurement mints a new `report_id`; aliases belong in a
separate, reviewable index and may advance.

`schema_version` has major.minor form.  A v1 reader must reject an unknown
major, may accept an unknown minor only when it ignores only optional fields,
and must preserve unknown fields when it is a round-trip tool.

## Required top-level fields

`profile_id`, `schema_version`, `identity`, `provenance`, `photometric`,
`electrical`, and `chip_encoding` are required.  `provenance.kind` is either
`datasheet_derived` or `measured`.  A measured artifact additionally requires
instrument model/serial/type, ISO-8601 date, fixture geometry, temperature,
drive conditions, and a stable raw-data pointer.  It is not valid to label a
PDF transcription as measured.

Each `photometric.channels` entry has `name` and may provide `chromaticity`,
`relative_y`, `dominant_wavelength_nm`, `peak_wavelength_nm`, and `response`.
Each numeric observation is an object with `value`, optional `unit`,
`qualifier`, and `source`.  The only qualifiers are `min`, `typical`, `max`,
`measured`, and `inferred`.  `source` names a repository-relative document,
page, and section/table.  Omitted data means unknown, never zero.

`electrical` is deliberately separate: channel current, forward voltage,
idle power, and current-vs-code data do not share a field with photometric Y.
`response.code_to_relative_light` is legal only when its input points are
actually documented or measured; it is not a gamma guess.

`chip_encoding.five_bit_semantics` is one of `secondary_slow_pwm`,
`current_gain`, `unknown`, or `not_applicable`.  This represents the chip's
documented semantics (B1), not the name "global current".

## Admission boundary

An artifact may be a catalog record with unavailable photometry, but only a
profile having usable finite xy/Y channel data can generate an `EmitterProfile`.
The validator therefore validates structure/provenance for all artifacts and
marks incomplete optical data as `not_runtime_admissible`; it does not turn
missing PDF information into a fallback profile.  Instrument accuracy and the
P10 hardware gate are separate from schema validity.
