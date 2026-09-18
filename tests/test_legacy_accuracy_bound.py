import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).parents[1] / "tools" / "bound_legacy_correction_accuracy.py"
SPEC = importlib.util.spec_from_file_location("bound_legacy_correction_accuracy", TOOL)
assert SPEC and SPEC.loader
BOUND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOUND)

# Optional: path to the pinned CIE 1931 2-degree CSV, for the tests that need
# real colour-matching functions. The payload is CC BY-SA and not vendored.
CIE_CSV = os.environ.get("DATASHEETS_CIE_CSV")


class DeltaE2000Test(unittest.TestCase):
    # Sharma, Wu & Dalal (2005), Table 1, pairs 1, 7, 17 and 34.
    PAIRS = (
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
        ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
        ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
    )

    def test_matches_the_published_reference_pairs(self) -> None:
        for lab1, lab2, expected in self.PAIRS:
            self.assertAlmostEqual(BOUND.delta_e_2000(lab1, lab2), expected, places=4)

    def test_is_zero_for_identical_colours(self) -> None:
        self.assertEqual(BOUND.delta_e_2000((50, 10, -20), (50, 10, -20)), 0.0)


class AdaptationTest(unittest.TestCase):
    def test_bradford_maps_source_white_onto_destination_white(self) -> None:
        dst = (1.0985, 1.0, 0.3558)  # illuminant A
        mapped = BOUND.mat_vec(BOUND.bradford(BOUND.D65_XYZ, dst), BOUND.D65_XYZ)
        for got, want in zip(mapped, dst):
            self.assertAlmostEqual(got, want, places=9)

    def test_srgb_primaries_device_scores_zero_uncorrected(self) -> None:
        # A device whose emitters are exactly the sRGB primaries has a D65
        # full-drive white, so the relative target needs no adaptation and the
        # uncorrected legacy drive reproduces every test colour.
        xys = [(0.64, 0.33), (0.30, 0.60), (0.15, 0.06)]
        lums = [0.2126729, 0.7151522, 0.0721750]
        matrix = BOUND.emitter_matrix(xys, lums)
        for error in BOUND.score(matrix, BOUND.MODELS["UncorrectedColor"]):
            self.assertLess(error, 0.05)

    def test_a_white_tinting_correction_is_penalized_under_a1(self) -> None:
        xys = [(0.64, 0.33), (0.30, 0.60), (0.15, 0.06)]
        lums = [0.2126729, 0.7151522, 0.0721750]
        matrix = BOUND.emitter_matrix(xys, lums)
        errors = BOUND.score(matrix, BOUND.MODELS["TypicalLEDStrip"])
        self.assertGreater(max(errors), 5.0)


class StatisticsTest(unittest.TestCase):
    def test_p95_interpolates_between_order_statistics(self) -> None:
        self.assertAlmostEqual(BOUND.p95(list(range(21))), 19.0)
        self.assertAlmostEqual(BOUND.p95([1.0, 2.0]), 1.95)


class CliTest(unittest.TestCase):
    def test_rejects_an_unpinned_cie_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "cie.csv"
            bad.write_text("500,1,1,1\n")
            with self.assertRaises(SystemExit):
                BOUND.main([str(bad)])

    def test_usage_error_without_arguments(self) -> None:
        self.assertEqual(BOUND.main([]), 2)


@unittest.skipUnless(
    CIE_CSV, "set DATASHEETS_CIE_CSV to the pinned CIE 1931 2-degree CSV"
)
class RealColourMatchingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        BOUND.verify_cie(Path(CIE_CSV))
        cls.cmf = BOUND.load_cmf(Path(CIE_CSV))
        cls.locus = BOUND.locus(cls.cmf)

    def test_emitter_xy_round_trips_its_dominant_wavelength(self) -> None:
        for dominant, fwhm in ((466.0, 20.0), (523.5, 30.0), (622.5, 18.0)):
            xy = BOUND.emitter_xy(self.cmf, self.locus, dominant, fwhm)
            self.assertAlmostEqual(
                BOUND.dominant_wavelength(xy, self.locus), dominant, places=3
            )

    def test_a_wider_emitter_is_less_saturated_at_the_same_dominant_wavelength(
        self,
    ) -> None:
        narrow = BOUND.emitter_xy(self.cmf, self.locus, 523.5, 20.0)
        wide = BOUND.emitter_xy(self.cmf, self.locus, 523.5, 40.0)
        e = BOUND.EQUAL_ENERGY
        distance = lambda xy: ((xy[0] - e[0]) ** 2 + (xy[1] - e[1]) ** 2) ** 0.5
        self.assertGreater(distance(narrow), distance(wide))

    def test_checked_in_outputs_are_current(self) -> None:
        self.assertEqual(BOUND.main([CIE_CSV, "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
