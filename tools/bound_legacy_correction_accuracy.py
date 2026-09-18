"""Bound the colour accuracy of FastLED's legacy corrections from datasheet data.

FastLED/FastLED#4035 asks P1 to quantify ``TypicalLEDStrip``,
``Typical8mmPixel`` and ``UncorrectedColor`` against datasheet-derived
profiles. The integrated-LED datasheets publish a *dominant-wavelength range*
and a *luminous-intensity range* per emitter, not chromaticity, so a single
derived profile would manufacture precision the PDFs lack. This tool instead
samples what the datasheets do state -- each range's ends and midpoint -- into
a grid of profiles, and reports the ΔE2000 each legacy model scores across
that grid. A grid is an inner bound on the continuous ranges, not a proof over
them.

Stated assumptions (not datasheet facts, and named in every output):

* Each emitter's spectrum is a Gaussian in wavelength whose FWHM lies in a
  per-technology interval (``FWHM_NM``). Its peak is solved so that its
  dominant wavelength (relative to the equal-energy white E) equals the
  datasheet value.
* Luminous intensity is proportional to Y at a common viewing geometry, so
  the mcd ratio is the relative Y of the three emitters.

Evaluation (A1 normalization, #4033): an ordinary buffer is linear sRGB
(B6/B8). The intended colour of code ``c`` is ``c/255`` through the sRGB
primaries, Bradford-adapted from D65 to the device's full-drive white, with
that white at Y=1. The legacy path drives each emitter linearly at
``c/255 * correction``. ΔE2000 is computed in CIELAB with the device white as
reference, over a black-safe neutral ramp, the primaries and the secondaries.

The CIE 1931 2-degree CMF table is the CIE 2019 dataset (CC BY-SA 4.0), not
redistributed here; the CLI refuses any payload whose SHA-256 differs.

    uv run python tools/bound_legacy_correction_accuracy.py CIE_xyz_1931_2deg.csv
    uv run python tools/bound_legacy_correction_accuracy.py CIE_xyz_1931_2deg.csv --check
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "measured-profiles" / "legacy-correction-accuracy-bound-v1.json"
REPORT = ROOT / "measured-profiles" / "LEGACY-ACCURACY-BOUND.md"
CIE_SHA256 = "fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1"

# A1 datasheet-derived profile budget (#4033): median / p95 ΔE2000.
BUDGET_MEDIAN = 3.0
BUDGET_P95 = 6.0

# Assumed FWHM intervals, nm (low, high): AlGaInP red, InGaN green, InGaN blue.
FWHM_NM = {"red": (15.0, 25.0), "green": (25.0, 40.0), "blue": (18.0, 30.0)}

# Legacy correction coefficients, FastLED src/color.h.
MODELS = {
    "UncorrectedColor": (1.0, 1.0, 1.0),
    "TypicalLEDStrip": (1.0, 176 / 255, 240 / 255),
    "Typical8mmPixel": (1.0, 224 / 255, 140 / 255),
}

# Datasheet rows transcribed in P1-CHARACTERIZATION.md ("Extracted
# integrated-package inventory"). Each channel: dominant wavelength range nm,
# luminous-intensity range mcd (equal bounds where one value is published).
PARTS = {
    "SK6812": {
        "red": ((620, 625), (700, 1000)),
        "green": ((522.5, 525), (1500, 2200)),
        "blue": ((467.5, 470), (700, 1000)),
    },
    "WS2812B": {
        "red": ((620, 625), (390, 420)),
        "green": ((522, 525), (660, 720)),
        "blue": ((465, 467), (180, 200)),
    },
    "WS2813A": {
        "red": ((620, 622), (480, 480)),
        "green": ((522, 525), (1500, 1500)),
        "blue": ((467, 470), (320, 320)),
    },
    "WS2813B": {
        "red": ((620, 622), (360, 360)),
        "green": ((522, 525), (1150, 1150)),
        "blue": ((467, 470), (220, 220)),
    },
    "WS2813C": {
        "red": ((620, 622), (120, 120)),
        "green": ((522, 525), (540, 540)),
        "blue": ((467, 470), (130, 130)),
    },
    "WS2813D": {
        "red": ((620, 622), (100, 100)),
        "green": ((522, 525), (420, 420)),
        "blue": ((467, 470), (110, 110)),
    },
    "WS2815": {
        "red": ((620, 625), (360, 360)),
        "green": ((515, 525), (1150, 1150)),
        "blue": ((465, 475), (220, 220)),
    },
    "WS2816B-2121": {
        "red": ((620, 625), (210, 360)),
        "green": ((522, 527), (420, 720)),
        "blue": ((470, 475), (70, 120)),
    },
    "GS8208 LED5050 option": {
        "red": ((615, 630), (450, 450)),
        "green": ((520, 535), (1300, 1300)),
        "blue": ((460, 475), (280, 280)),
    },
}
CHANNELS = ("red", "green", "blue")

# Test colours as 8-bit codes: black-safe neutral ramp, primaries, secondaries.
NEUTRALS = [(v, v, v) for v in (32, 64, 128, 192, 255)]
CHROMATICS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (0, 255, 255),
    (255, 0, 255),
    (255, 255, 0),
]
TEST_COLOURS = NEUTRALS + CHROMATICS

SRGB_TO_XYZ = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)
D65_XYZ = (0.95047, 1.0, 1.08883)
BRADFORD = (
    (0.8951, 0.2664, -0.1614),
    (-0.7502, 1.7135, 0.0367),
    (0.0389, -0.0685, 1.0296),
)
EQUAL_ENERGY = (1 / 3, 1 / 3)


# ---------------------------------------------------------------- linear algebra


def mat_vec(m, v):
    return tuple(sum(m[r][c] * v[c] for c in range(3)) for r in range(3))


def mat_mul(a, b):
    return tuple(
        tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3))
        for r in range(3)
    )


def mat_inv(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        raise ValueError("singular matrix")
    return (
        ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det),
        ((f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det),
        ((d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det),
    )


def bradford(src_white, dst_white):
    """Bradford chromatic-adaptation matrix taking src_white to dst_white."""
    s = mat_vec(BRADFORD, src_white)
    d = mat_vec(BRADFORD, dst_white)
    scale = ((d[0] / s[0], 0, 0), (0, d[1] / s[1], 0), (0, 0, d[2] / s[2]))
    return mat_mul(mat_inv(BRADFORD), mat_mul(scale, BRADFORD))


# ------------------------------------------------------------------- CIE colour


def load_cmf(path: Path) -> dict[int, tuple[float, float, float]]:
    cmf: dict[int, tuple[float, float, float]] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) != 4:
            raise ValueError(f"CIE CMF row {line_number} must have four columns")
        wavelength = int(float(parts[0]))
        values = tuple(
            float(p) if p.strip().lower() != "nan" else 0.0 for p in parts[1:]
        )
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"CIE CMF row {line_number} is not finite")
        if wavelength in cmf:
            raise ValueError(f"CIE CMF duplicate wavelength {wavelength}")
        cmf[wavelength] = values
    return cmf


def gaussian_xy(cmf, peak_nm: float, fwhm_nm: float) -> tuple[float, float]:
    sigma = fwhm_nm / (2 * math.sqrt(2 * math.log(2)))
    x = y = z = 0.0
    for wavelength, (xb, yb, zb) in cmf.items():
        s = math.exp(-0.5 * ((wavelength - peak_nm) / sigma) ** 2)
        x += s * xb
        y += s * yb
        z += s * zb
    total = x + y + z
    if total <= 0:
        raise ValueError("spectrum integrates to zero")
    return x / total, y / total


def locus(cmf) -> list[tuple[int, float]]:
    """(wavelength, hue angle about E) along the spectral locus, 380–700 nm."""
    points = []
    for wavelength in range(380, 701):
        xb, yb, zb = cmf[wavelength]
        total = xb + yb + zb
        x, y = xb / total, yb / total
        points.append(
            (wavelength, math.atan2(y - EQUAL_ENERGY[1], x - EQUAL_ENERGY[0]))
        )
    return points


def dominant_wavelength(xy, locus_points) -> float:
    """Dominant wavelength of a spectral (non-purple) chromaticity about E."""
    angle = math.atan2(xy[1] - EQUAL_ENERGY[1], xy[0] - EQUAL_ENERGY[0])
    # Hue angle decreases monotonically with wavelength over 380–700 nm, with
    # one wrap from -pi to +pi in the blue; unwrap so the list is monotonic.
    unwrapped = []
    previous = None
    offset = 0.0
    for wavelength, a in locus_points:
        if previous is not None and a - previous > math.pi:
            offset -= 2 * math.pi
        unwrapped.append((wavelength, a + offset))
        previous = a
    for candidate in (angle, angle - 2 * math.pi, angle + 2 * math.pi):
        for (w0, a0), (w1, a1) in zip(unwrapped, unwrapped[1:]):
            if min(a0, a1) <= candidate <= max(a0, a1) and a0 != a1:
                return w0 + (candidate - a0) / (a1 - a0) * (w1 - w0)
    raise ValueError("chromaticity is on the purple line; no dominant wavelength")


def emitter_xy(
    cmf, locus_points, dominant_nm: float, fwhm_nm: float
) -> tuple[float, float]:
    """xy of the Gaussian emitter of the given FWHM whose dominant wavelength is dominant_nm."""
    lo, hi = dominant_nm - 40.0, dominant_nm + 40.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if (
            dominant_wavelength(gaussian_xy(cmf, mid, fwhm_nm), locus_points)
            < dominant_nm
        ):
            lo = mid
        else:
            hi = mid
    return gaussian_xy(cmf, 0.5 * (lo + hi), fwhm_nm)


# --------------------------------------------------------------- CIELAB / ΔE2000


def xyz_to_lab(xyz, white):
    def f(t):
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = (f(xyz[i] / white[i]) for i in range(3))
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e_2000(lab1, lab2) -> float:
    """CIEDE2000 (Sharma, Wu & Dalal 2005), kL = kC = kH = 1."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if c2p else 0.0
    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dhp_big = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp / 2))
    lp_bar = (l1 + l2) / 2
    cp_bar = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_bar = (h1p + h2p + 360) / 2
    else:
        hp_bar = (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(hp_bar - 30))
        + 0.24 * math.cos(math.radians(2 * hp_bar))
        + 0.32 * math.cos(math.radians(3 * hp_bar + 6))
        - 0.20 * math.cos(math.radians(4 * hp_bar - 63))
    )
    d_theta = 30 * math.exp(-(((hp_bar - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cp_bar**7 / (cp_bar**7 + 25**7))
    sl = 1 + 0.015 * (lp_bar - 50) ** 2 / math.sqrt(20 + (lp_bar - 50) ** 2)
    sc = 1 + 0.045 * cp_bar
    sh = 1 + 0.015 * cp_bar * t
    rt = -math.sin(math.radians(2 * d_theta)) * rc
    return math.sqrt(
        (dlp / sl) ** 2
        + (dcp / sc) ** 2
        + (dhp_big / sh) ** 2
        + rt * (dcp / sc) * (dhp_big / sh)
    )


# ---------------------------------------------------------------- evaluation


def emitter_matrix(xys, luminances):
    """3x3 matrix whose columns are the emitters' XYZ, device white at Y=1."""
    total = sum(luminances)
    cols = []
    for (x, y), lum in zip(xys, luminances):
        big_y = lum / total
        cols.append((x / y * big_y, big_y, (1 - x - y) / y * big_y))
    return tuple(tuple(cols[c][r] for c in range(3)) for r in range(3))


def score(matrix, correction) -> list[float]:
    """ΔE2000 of the legacy path for every test colour against the relative-colorimetric target."""
    device_white = mat_vec(matrix, (1.0, 1.0, 1.0))
    adapt = bradford(D65_XYZ, device_white)
    errors = []
    for code in TEST_COLOURS:
        linear = tuple(v / 255 for v in code)
        target = mat_vec(adapt, mat_vec(SRGB_TO_XYZ, linear))
        drive = tuple(linear[i] * correction[i] for i in range(3))
        actual = mat_vec(matrix, drive)
        errors.append(
            delta_e_2000(
                xyz_to_lab(target, device_white), xyz_to_lab(actual, device_white)
            )
        )
    return errors


def score_absolute(matrix, correction) -> list[float]:
    """Supplementary, not A1: ΔE2000 against the sRGB colour with no adaptation.

    Target and reference white are D65 (white at Y=1); the device's full-drive
    white is also Y=1. This is the goal the legacy corrections were designed
    for -- pulling the device white toward D65 -- which A1's relative
    colorimetry deliberately does not reward.
    """
    errors = []
    for code in TEST_COLOURS:
        linear = tuple(v / 255 for v in code)
        target = mat_vec(SRGB_TO_XYZ, linear)
        drive = tuple(linear[i] * correction[i] for i in range(3))
        actual = mat_vec(matrix, drive)
        errors.append(delta_e_2000(xyz_to_lab(target, D65_XYZ), xyz_to_lab(actual, D65_XYZ)))
    return errors


def p95(values) -> float:
    ordered = sorted(values)
    rank = 0.95 * (len(ordered) - 1)
    low = math.floor(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (rank - low) * (ordered[high] - ordered[low])


def evaluate(cmf) -> dict:
    locus_points = locus(cmf)
    rows = []
    for part, channels in PARTS.items():
        # Per channel: every (dominant wavelength, FWHM) corner -> xy.
        xy_options = {}
        for name in CHANNELS:
            (d_lo, d_hi), _ = channels[name]
            w_lo, w_hi = FWHM_NM[name]
            xy_options[name] = [
                emitter_xy(cmf, locus_points, d, w)
                for d in (d_lo, (d_lo + d_hi) / 2, d_hi)
                for w in (w_lo, (w_lo + w_hi) / 2, w_hi)
            ]
        # min, mid and max, so the nominal (mid) profile is one of the samples.
        lum_options = {
            name: sorted(
                {
                    channels[name][1][0],
                    sum(channels[name][1]) / 2,
                    channels[name][1][1],
                }
            )
            for name in CHANNELS
        }
        nominal_xy = [
            xy_options[name][4] for name in CHANNELS
        ]  # mid wavelength, mid FWHM
        nominal_lum = [sum(channels[name][1]) / 2 for name in CHANNELS]
        nominal = emitter_matrix(nominal_xy, nominal_lum)
        per_model = {}
        for model, correction in MODELS.items():
            medians, p95s = [], []
            for xys in itertools.product(*(xy_options[n] for n in CHANNELS)):
                for lums in itertools.product(*(lum_options[n] for n in CHANNELS)):
                    errors = score(emitter_matrix(xys, lums), correction)
                    medians.append(statistics.median(errors))
                    p95s.append(p95(errors))
            nominal_errors = score(nominal, correction)
            absolute_errors = score_absolute(nominal, correction)
            per_model[model] = {
                "nominal_median": round(statistics.median(nominal_errors), 2),
                "nominal_p95": round(p95(nominal_errors), 2),
                "median_range": [round(min(medians), 2), round(max(medians), 2)],
                "median_spread": round(max(medians) - min(medians), 2),
                "absolute_nominal_median": round(statistics.median(absolute_errors), 2),
                "absolute_nominal_p95": round(p95(absolute_errors), 2),
                "p95_range": [round(min(p95s), 2), round(max(p95s), 2)],
                "within_budget_at_every_sample": max(medians) <= BUDGET_MEDIAN
                and max(p95s) <= BUDGET_P95,
                "outside_budget_at_every_sample": min(medians) > BUDGET_MEDIAN
                or min(p95s) > BUDGET_P95,
            }
        rows.append(
            {
                "part": part,
                "sampled_profiles": len(xy_options["red"]) ** 3
                * math.prod(len(v) for v in lum_options.values()),
                "models": per_model,
            }
        )
    return {
        "kind": "datasheet_bound_not_measurement",
        "issue": "FastLED/FastLED#4035",
        "assumptions": {
            "spectrum": "Gaussian per emitter; peak solved so dominant wavelength (about equal-energy E) matches the datasheet",
            "fwhm_nm": {k: list(v) for k, v in FWHM_NM.items()},
            "relative_y": "proportional to published luminous intensity (common viewing geometry)",
        },
        "evaluation": {
            "source": "linear sRGB (B6/B8 default for ordinary buffers)",
            "target": "Bradford D65 -> device full-drive white, white at Y=1 (A1)",
            "metric": "CIEDE2000 in CIELAB with device white as reference",
            "test_colours": [list(c) for c in TEST_COLOURS],
            "budget": {"median": BUDGET_MEDIAN, "p95": BUDGET_P95},
            "sampling": "grid, not the continuum: dominant wavelength {min, mid, max} x FWHM {low, mid, high} x intensity {min, mid, max} per channel",
        },
        "models": {k: [round(v, 6) for v in c] for k, c in MODELS.items()},
        "rows": rows,
    }


def render_report(data: dict) -> str:
    lines = [
        "# Legacy-correction accuracy, bounded from datasheet data",
        "",
        "Generated by `tools/bound_legacy_correction_accuracy.py` for FastLED/FastLED#4035.",
        "**This is a bound, not a measurement.** The datasheets publish dominant-wavelength",
        "and luminous-intensity ranges, not chromaticity, so the ranges are sampled on a grid",
        "(each channel's dominant wavelength min/mid/max × FWHM low/mid/high × intensity",
        "min/mid/max) and every grid profile is scored, under two stated assumptions:",
        "",
        "- each emitter's spectrum is a Gaussian whose dominant wavelength (about equal-energy",
        f"  white E) matches the datasheet, with FWHM red {FWHM_NM['red'][0]:g}–{FWHM_NM['red'][1]:g} nm,",
        f"  green {FWHM_NM['green'][0]:g}–{FWHM_NM['green'][1]:g} nm, blue {FWHM_NM['blue'][0]:g}–{FWHM_NM['blue'][1]:g} nm (assumed, typical of",
        "  AlGaInP / InGaN emitters; not from the datasheets);",
        "- luminous intensity is proportional to Y at a common viewing geometry.",
        "",
        "Evaluation follows A1: an ordinary buffer is linear sRGB (B6/B8); the target is the",
        "sRGB colour Bradford-adapted from D65 to the device's full-drive white (Y=1); the",
        "legacy path drives each emitter at `code/255 × correction`. ΔE2000 over a black-safe",
        "neutral ramp (32–255), RGB primaries and CMY secondaries. Budget for a",
        f"datasheet-derived profile: median ≤ {BUDGET_MEDIAN:g}, p95 ≤ {BUDGET_P95:g}.",
        "",
        "`nominal` is the grid's centre point: mid wavelength, mid FWHM, mid intensity. The",
        "ranges are the minimum and maximum of each statistic over the sampled grid. They are",
        "not a proof over the continuous ranges: a grid can miss a worse or better interior",
        "point, so each range is an inner bound on the true one.",
        "",
        "| part | model | nominal median | nominal p95 | median range | median spread | p95 range | verdict |",
        "| --- | --- | ---: | ---: | --- | ---: | --- | --- |",
    ]
    for row in data["rows"]:
        for model, r in row["models"].items():
            if r["within_budget_at_every_sample"]:
                verdict = "within budget at every sample"
            elif r["outside_budget_at_every_sample"]:
                verdict = "outside budget at every sample"
            else:
                verdict = "samples straddle the budget"
            lines.append(
                f"| {row['part']} | {model} | {r['nominal_median']:.2f} | {r['nominal_p95']:.2f} | "
                f"{r['median_range'][0]:.2f}–{r['median_range'][1]:.2f} | {r['median_spread']:.2f} | "
                f"{r['p95_range'][0]:.2f}–{r['p95_range'][1]:.2f} | {verdict} |"
            )
    cells = [(row["part"], m, r) for row in data["rows"] for m, r in row["models"].items()]
    wide = sum(1 for _, _, r in cells if r["median_spread"] > BUDGET_MEDIAN)
    outside = sum(1 for _, _, r in cells if r["outside_budget_at_every_sample"])
    inside = sum(1 for _, _, r in cells if r["within_budget_at_every_sample"])
    lines += [
        "",
        "## What this establishes",
        "",
        f"- **Datasheet ranges cannot pin accuracy to the A1 budget.** In {wide} of {len(cells)} part/model",
        f"  cells the median ΔE2000 over the sampled grid alone spans more than the whole",
        f"  {BUDGET_MEDIAN:g} median budget. A sampled spread can only understate the continuous one,",
        "  so this holds for the ranges themselves: no single datasheet-derived profile could",
        "  be defended at that budget, and a runtime profile needs xy or spectral data the",
        "  PDFs do not publish.",
        f"- **Legacy models under A1:** {outside} of {len(cells)} cells are outside budget at every",
        f"  sampled profile, {inside} within budget at every one, and the rest straddle it. These",
        "  verdicts are over the grid, not proven over the continuous ranges.",
        "  `TypicalLEDStrip` and `Typical8mmPixel` score worse than `UncorrectedColor` under A1",
        "  because A1 is relative colorimetry: the target is adapted to the device's own",
        "  full-drive white, so a correction that tints that white is penalized. The",
        "  supplementary absolute table below scores the goal those corrections were built for.",
        "",
        "## Supplementary: absolute colorimetry (not A1)",
        "",
        "Target and reference white are D65 with no adaptation; nominal profile only. Context",
        "for the legacy corrections' design intent, not an A1 acceptance number.",
        "",
        "| part | model | median | p95 |",
        "| --- | --- | ---: | ---: |",
    ]
    for part, model, r in cells:
        lines.append(f"| {part} | {model} | {r['absolute_nominal_median']:.2f} | {r['absolute_nominal_p95']:.2f} |")
    lines.append("")
    return "\n".join(lines)


def verify_cie(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != CIE_SHA256:
        raise SystemExit(f"CIE CMF payload SHA-256 {digest} != pinned {CIE_SHA256}")


def main(argv: list[str]) -> int:
    if not argv or len(argv) > 2 or (len(argv) == 2 and argv[1] != "--check"):
        print(__doc__, file=sys.stderr)
        return 2
    cie = Path(argv[0])
    verify_cie(cie)
    data = evaluate(load_cmf(cie))
    rendered = json.dumps(data, indent=2) + "\n"
    report = render_report(data)
    if len(argv) == 2:
        ok = OUTPUT.read_text() == rendered and REPORT.read_text() == report
        print("up to date" if ok else "stale: regenerate", file=sys.stderr)
        return 0 if ok else 1
    OUTPUT.write_text(rendered)
    REPORT.write_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
