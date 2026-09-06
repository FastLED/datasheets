"""Digitize SK9822 Rev. 01 page-7 vector spectra and integrate CIE 1931 xy.

The CIE input is the CIE 2019 2-degree CMF CSV, CC BY-SA 4.0:
https://files.cie.co.at/Publications-datasets/CIE_xyz_1931_2deg.csv
Its required SHA-256 is fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1.
Run with ``uv run --with pymupdf python tools/digitize_sk9822_spectrum.py PDF CSV``.
"""

import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


PLOT_LEFT, PLOT_RIGHT = 342.06, 519.36
PLOT_TOP, PLOT_BOTTOM = 420.0, 531.78
COLORS = {(1.0, 0.0, 0.0): "red", (0.0, 1.0, 0.0): "green", (0.0, 0.0, 1.0): "blue"}
SK9822_PDF_SHA256 = "c9973c201856c27c88f431568a9a308df3f181f755444734eb2f62d908b6b37e"
CIE_SHA256 = "fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1"


def extract(pdf: Path) -> list[tuple[str, float, float]]:
    import pymupdf

    page = pymupdf.open(pdf)[6]
    rows: list[tuple[str, float, float]] = []
    for drawing in page.get_drawings():
        if drawing["color"] not in COLORS or not drawing["items"] or drawing["items"][0][0] != "qu":
            continue
        rect = drawing["rect"]
        if not (PLOT_LEFT <= rect.x0 <= PLOT_RIGHT and PLOT_LEFT <= rect.x1 <= PLOT_RIGHT and rect.y1 >= PLOT_TOP and rect.y0 <= PLOT_BOTTOM):
            continue
        wavelength = 400 + ((rect.x0 + rect.x1) / 2 - PLOT_LEFT) * 400 / (PLOT_RIGHT - PLOT_LEFT)
        relative = max(0.0, min(1.0, (PLOT_BOTTOM - (rect.y0 + rect.y1) / 2) / (PLOT_BOTTOM - PLOT_TOP)))
        rows.append((COLORS[drawing["color"]], wavelength, relative))
    return sorted(rows)


def validate_extraction(rows: list[tuple[str, float, float]]) -> None:
    channels: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for channel, wavelength, relative in rows:
        if channel not in COLORS.values():
            raise ValueError(f"extraction has unknown channel {channel!r}")
        if not math.isfinite(wavelength) or not math.isfinite(relative):
            raise ValueError("extraction samples must be finite")
        channels[channel].append((wavelength, relative))
    if set(channels) != set(COLORS.values()):
        raise ValueError("extraction must contain exactly red, green, and blue channels")
    for channel, samples in channels.items():
        if len(samples) < 2:
            raise ValueError(f"extraction channel {channel} requires at least two samples")
        wavelengths = [wavelength for wavelength, _ in samples]
        if len(wavelengths) != len(set(wavelengths)):
            raise ValueError(f"extraction channel {channel} has duplicate wavelengths")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interpolate(rows: list[tuple[float, float]], wavelength: float) -> float:
    if wavelength < rows[0][0] or wavelength > rows[-1][0]:
        return 0.0
    for (left_wavelength, left_value), (right_wavelength, right_value) in zip(rows, rows[1:]):
        if left_wavelength <= wavelength <= right_wavelength:
            if wavelength == left_wavelength:
                return left_value
            return left_value + (right_value - left_value) * (wavelength - left_wavelength) / (right_wavelength - left_wavelength)
    return rows[-1][1]


def cmf_at(cmf: dict[int, tuple[float, float, float]], wavelength: float) -> tuple[float, float, float]:
    lower = int(wavelength)
    if wavelength == lower:
        return cmf[lower]
    fraction = wavelength - lower
    return tuple(cmf[lower][index] + fraction * (cmf[lower + 1][index] - cmf[lower][index]) for index in range(3))


def integrate_rows(rows: list[tuple[float, float]], cmf: dict[int, tuple[float, float, float]]) -> tuple[float, float]:
    rows = sorted(rows)
    if len(rows) < 2:
        raise ValueError("SPD requires at least two samples")
    if any(not math.isfinite(wavelength) or not math.isfinite(value) or value < 0 for wavelength, value in rows):
        raise ValueError("SPD samples must have finite wavelengths and non-negative finite values")
    if any(left[0] == right[0] for left, right in zip(rows, rows[1:])):
        raise ValueError("SPD wavelengths must be unique")
    required_cmf = range(math.floor(rows[0][0]), math.ceil(rows[-1][0]) + 1)
    if any(wavelength not in cmf for wavelength in required_cmf):
        raise ValueError("CIE CMF coverage is incomplete for SPD support")
    knots = sorted({wavelength for wavelength, _ in rows} | {float(wavelength) for wavelength in cmf if rows[0][0] <= wavelength <= rows[-1][0]})
    xyz = [0.0, 0.0, 0.0]
    for left, right in zip(knots, knots[1:]):
        midpoint = (left + right) / 2
        for weight, wavelength in ((1, left), (4, midpoint), (1, right)):
            spd = interpolate(rows, wavelength)
            for index, value in enumerate(cmf_at(cmf, wavelength)):
                xyz[index] += (right - left) * weight * spd * value / 6
    total = sum(xyz)
    if total <= 0:
        raise ValueError("SPD integration produced zero tristimulus total")
    return xyz[0] / total, xyz[1] / total


def sensitivity(rows: list[tuple[float, float]], cmf: dict[int, tuple[float, float, float]]) -> dict[str, tuple[float, float]]:
    values = [integrate_rows([(wavelength + shift, max(0.0, value + ordinate)) for wavelength, value in rows], cmf)
              for shift in (-1.0, 0.0, 1.0) for ordinate in (-0.01, 0.0, 0.01)]
    return {"x": (min(value[0] for value in values), max(value[0] for value in values)), "y": (min(value[1] for value in values), max(value[1] for value in values))}


def load_cmf(cie_path: Path) -> dict[int, tuple[float, float, float]]:
    cmf: dict[int, tuple[float, float, float]] = {}
    with cie_path.open() as stream:
        for line_number, row in enumerate(csv.reader(stream), start=1):
            if len(row) != 4:
                raise ValueError(f"CIE CMF row {line_number} must have four columns")
            if line_number == 1 and row[0].strip().lower() in {"wavelength", "wavelength_nm"}:
                raise ValueError("CIE CMF header is not permitted")
            try:
                wavelength = int(row[0])
                values = tuple(float(value) for value in row[1:])
            except ValueError as error:
                raise ValueError(f"CIE CMF row {line_number} is not numeric") from error
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"CIE CMF finite values required at row {line_number}")
            if wavelength in cmf:
                raise ValueError(f"CIE CMF duplicate wavelength {wavelength}")
            cmf[wavelength] = values
    return cmf


def load_spd(spd_path: Path) -> dict[str, list[tuple[float, float]]]:
    channels: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with spd_path.open() as stream:
        reader = csv.DictReader(stream)
        expected_header = ["channel", "wavelength_nm", "relative_spd"]
        if reader.fieldnames != expected_header:
            raise ValueError("SPD CSV header must be channel,wavelength_nm,relative_spd")
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(row[field] in (None, "") for field in expected_header):
                raise ValueError(f"SPD CSV row {line_number} is incomplete")
            try:
                wavelength = float(row["wavelength_nm"])
                relative = float(row["relative_spd"])
            except ValueError as error:
                raise ValueError(f"SPD CSV row {line_number} is not numeric") from error
            if not math.isfinite(wavelength) or not math.isfinite(relative):
                raise ValueError(f"SPD CSV finite values required at row {line_number}")
            if any(existing == wavelength for existing, _ in channels[row["channel"]]):
                raise ValueError(f"SPD CSV duplicate wavelength for {row['channel']}")
            channels[row["channel"]].append((wavelength, relative))
    return channels


def integrate(spd_path: Path, cie_path: Path) -> dict[str, tuple[float, float]]:
    cmf = load_cmf(cie_path)
    return {channel: integrate_rows(rows, cmf) for channel, rows in load_spd(spd_path).items()}


def main() -> int:
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--integrate":
            spd_path, cie_path = Path(sys.argv[2]), Path(sys.argv[3])
            if sha256(cie_path) != CIE_SHA256:
                print("CIE CSV SHA-256 does not match the pinned CIE 2019 data set", file=sys.stderr)
                return 1
            cmf, spd = load_cmf(cie_path), load_spd(spd_path)
            print(json.dumps({channel: {"xy": integrate_rows(rows, cmf), "graph_resolution_sensitivity": sensitivity(rows, cmf)} for channel, rows in spd.items()}, indent=2, sort_keys=True))
            return 0
        if len(sys.argv) != 3:
            print("usage: digitize_sk9822_spectrum.py INPUT.pdf OUTPUT.csv | --integrate SPD.csv CIE.csv", file=sys.stderr)
            return 2
        pdf_path = Path(sys.argv[1])
        if sha256(pdf_path) != SK9822_PDF_SHA256:
            print("SK9822 PDF SHA-256 does not match the pinned Rev. 01 payload", file=sys.stderr)
            return 1
        rows = extract(pdf_path)
        validate_extraction(rows)
        with Path(sys.argv[2]).open("w", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("channel", "wavelength_nm", "relative_spd"))
            writer.writerows((channel, f"{wavelength:.6f}", f"{relative:.6f}") for channel, wavelength, relative in rows)
        return 0
    except (OSError, ValueError, csv.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
