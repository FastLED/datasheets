import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL = Path(__file__).parents[1] / "tools" / "digitize_sk9822_spectrum.py"
SPEC = importlib.util.spec_from_file_location("digitize_sk9822_spectrum", TOOL)
assert SPEC and SPEC.loader
SPECTRUM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SPECTRUM)


class Sk9822SpectrumTest(unittest.TestCase):
    def test_integrate_relative_spd_normalizes_to_xy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spd = root / "spd.csv"
            cie = root / "cie.csv"
            with spd.open("w", newline="") as stream:
                csv.writer(stream).writerows((("channel", "wavelength_nm", "relative_spd"), ("red", 500, 1), ("red", 501, 1)))
            with cie.open("w", newline="") as stream:
                csv.writer(stream).writerows(((500, 1, 2, 3), (501, 1, 2, 3)))
            self.assertEqual(SPECTRUM.integrate(spd, cie)["red"], (1 / 6, 1 / 3))

    def test_piecewise_linear_integration_is_invariant_to_spd_resampling(self) -> None:
        cmf = {500: (1.0, 2.0, 3.0), 501: (2.0, 1.0, 1.0), 502: (1.0, 1.0, 2.0)}
        coarse = [(500.0, 0.0), (502.0, 1.0)]
        refined = [(500.0, 0.0), (501.0, 0.5), (502.0, 1.0)]
        expected = SPECTRUM.integrate_rows(coarse, cmf)
        actual = SPECTRUM.integrate_rows(refined, cmf)
        self.assertAlmostEqual(actual[0], expected[0], places=12)
        self.assertAlmostEqual(actual[1], expected[1], places=12)

    def test_sensitivity_is_reported_from_the_same_integration_model(self) -> None:
        cmf = {500: (1.0, 2.0, 3.0), 501: (2.0, 1.0, 1.0), 502: (1.0, 1.0, 2.0), 503: (1.0, 1.0, 1.0)}
        bounds = SPECTRUM.sensitivity([(501.0, 0.5), (502.0, 1.0)], cmf)
        self.assertLessEqual(bounds["x"][0], bounds["x"][1])
        self.assertLessEqual(bounds["y"][0], bounds["y"][1])

    def test_cli_rejects_unpinned_cie_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad_cie = Path(directory) / "cie.csv"
            bad_cie.write_text("500,1,1,1\n")
            with patch("sys.argv", [str(TOOL), "--integrate", "missing.csv", str(bad_cie)]):
                self.assertEqual(SPECTRUM.main(), 1)

    def test_integrate_rows_rejects_malformed_spd_samples(self) -> None:
        cmf = {500: (1.0, 1.0, 1.0), 501: (1.0, 1.0, 1.0)}
        for rows in ([(500.0, 1.0)], [(500.0, 1.0), (500.0, 0.5)], [(500.0, -0.1), (501.0, 1.0)], [(500.0, float("nan")), (501.0, 1.0)]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    SPECTRUM.integrate_rows(rows, cmf)

    def test_integrate_rows_requires_cmf_coverage_and_nonzero_xyz(self) -> None:
        rows = [(500.0, 0.5), (501.0, 1.0)]
        with self.assertRaisesRegex(ValueError, "coverage"):
            SPECTRUM.integrate_rows(rows, {500: (1.0, 1.0, 1.0)})
        with self.assertRaisesRegex(ValueError, "zero tristimulus"):
            SPECTRUM.integrate_rows(rows, {500: (0.0, 0.0, 0.0), 501: (0.0, 0.0, 0.0)})

    def test_extraction_admission_requires_complete_finite_rgb_curves(self) -> None:
        valid = [
            (channel, wavelength, 0.5)
            for channel in ("red", "green", "blue")
            for wavelength in (500.0, 501.0)
        ]
        SPECTRUM.validate_extraction(valid)
        invalid_cases = (
            valid[:4],
            valid[:5],
            valid + [("red", 500.0, 0.1)],
            valid + [("white", 502.0, 0.1)],
            valid[:-1] + [("blue", float("nan"), 0.5)],
            valid[:-1] + [("blue", 501.0, float("inf"))],
        )
        for rows in invalid_cases:
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(ValueError, "extraction"):
                    SPECTRUM.validate_extraction(rows)

    def test_load_spd_rejects_bad_header_rows_duplicates_and_nonfinite_values(self) -> None:
        cases = (
            ("channel,wavelength_nm,value\nred,500,1\n", "SPD CSV header"),
            ("channel,wavelength_nm,relative_spd\nred,500\n", "SPD CSV row"),
            ("channel,wavelength_nm,relative_spd\nred,500,1\nred,500,0.5\n", "SPD CSV duplicate"),
            ("channel,wavelength_nm,relative_spd\nred,500,nan\n", "SPD CSV finite"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spd.csv"
            for content, diagnostic in cases:
                with self.subTest(diagnostic=diagnostic):
                    path.write_text(content)
                    with self.assertRaisesRegex(ValueError, diagnostic):
                        SPECTRUM.load_spd(path)

    def test_load_cmf_rejects_header_rows_duplicates_and_nonfinite_values(self) -> None:
        cases = (
            ("wavelength,x,y,z\n", "CIE CMF header"),
            ("500,1,2\n", "CIE CMF row"),
            ("500,1,2,3\n500,1,2,3\n", "CIE CMF duplicate"),
            ("500,1,nan,3\n", "CIE CMF finite"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cie.csv"
            for content, diagnostic in cases:
                with self.subTest(diagnostic=diagnostic):
                    path.write_text(content)
                    with self.assertRaisesRegex(ValueError, diagnostic):
                        SPECTRUM.load_cmf(path)
