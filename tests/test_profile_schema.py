import importlib.util
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


TOOL = Path(__file__).parents[1] / "tools" / "check_profile_artifacts.py"
SPEC = importlib.util.spec_from_file_location("check_profile_artifacts", TOOL)
assert SPEC and SPEC.loader
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def profile() -> dict:
    return {
        "schema_version": "1.0", "profile_id": "ws2812b/5050/none/datasheet-r1",
        "identity": {"part": "ws2812b", "package_variant": "5050", "w_channel_variant": "none", "report_id": "datasheet-r1"},
        "provenance": {"kind": "datasheet_derived", "report_id": "datasheet-r1", "source_documents": ["worldsemi/addressable-led/WS2812B/datasheet.pdf"]},
        "photometric": {"channels": [{"name": "red", "runtime_admissible": False}]}, "electrical": {"channels": []},
        "chip_encoding": {"five_bit_semantics": "not_applicable"},
    }


class ProfileSchemaTest(unittest.TestCase):
    def test_runtime_admission_requires_complete_declared_channel_set(self) -> None:
        value = profile()
        value["chip_encoding"]["native_code_depth"] = 8
        value["runtime_admissible"] = False
        value["topology"] = "rgb"
        self.assertEqual(CHECK.validate_artifact(value, "fixture"), [])
        value["runtime_admissible"] = True
        self.assertIn("complete", " ".join(CHECK.validate_artifact(value, "fixture")))

    def test_json_loader_rejects_non_json_numeric_constants(self) -> None:
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError):
                CHECK.parse_artifact('{"value": ' + literal + '}')

    def test_json_loader_rejects_duplicate_keys_at_every_depth(self) -> None:
        for text in ('{"schema_version":"1.0","schema_version":"1.0"}', '{"provenance":{"kind":"datasheet_derived","kind":"measured"}}'):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                    CHECK.parse_artifact(text)

    def test_runtime_admission_requires_xy_simplex_and_positive_relative_y(self) -> None:
        value = profile()
        value["chip_encoding"]["native_code_depth"] = 8
        value["runtime_admissible"] = True
        value["topology"] = "rgb"
        source = {"path": "x.pdf", "page": 1, "section": "x"}
        value["photometric"]["channels"] = [
            {"name": name, "runtime_admissible": True,
             "chromaticity": {"x": {"value": x, "qualifier": "measured", "source": source}, "y": {"value": y, "qualifier": "measured", "source": source}},
             "relative_y": {"value": relative_y, "qualifier": "measured", "source": source}}
            for name, x, y, relative_y in (("red", -0.1, 0.4, 1.0), ("green", 0.7, 0.4, 1.0), ("blue", 0.2, 0.3, 0.0))
        ]
        errors = " ".join(CHECK.validate_artifact(value, "fixture"))
        self.assertIn("chromaticity must be inside the CIE xy simplex", errors)
        self.assertIn("relative_y must be positive", errors)

    def test_range_observations_require_matching_qualifiers_and_order(self) -> None:
        value = profile()
        value["chip_encoding"]["native_code_depth"] = 8
        source = {"path": "x.pdf", "page": 1, "section": "x"}
        value["photometric"]["channels"][0]["luminous_intensity_mcd_range"] = {
            "min": {"value": 3, "qualifier": "max", "source": source},
            "typical": {"value": 1, "qualifier": "typical", "source": source},
            "max": {"value": 2, "qualifier": "max", "source": source},
        }
        errors = " ".join(CHECK.validate_artifact(value, "fixture"))
        self.assertIn("range key min must match qualifier", errors)
        self.assertIn("range observations must satisfy min <= typical <= max", errors)

    def test_full_drive_white_chromaticity_requires_xy_simplex(self) -> None:
        value = profile()
        value["chip_encoding"]["native_code_depth"] = 8
        source = {"path": "x.pdf", "page": 1, "section": "x"}
        value["photometric"]["full_drive_white_chromaticity"] = {
            "x": {"value": 0.8, "qualifier": "typical", "source": source},
            "y": {"value": 0.3, "qualifier": "typical", "source": source},
        }
        self.assertIn("full-drive white chromaticity must be inside the CIE xy simplex", " ".join(CHECK.validate_artifact(value, "fixture")))

    def test_admission_combines_schema_and_identity_invariants(self) -> None:
        value = profile()
        value["chip_encoding"]["native_code_depth"] = 8
        self.assertEqual(CHECK.validate_artifact(value, "fixture"), [])
        value["identity"]["report_id"] = "different"
        self.assertIn("identity", " ".join(CHECK.validate_artifact(value, "fixture")))
        value = profile()
        value["unexpected"] = True
        self.assertTrue(CHECK.validate_artifact(value, "fixture"))
        for malformed in (None, [], {"identity": []}):
            self.assertTrue(CHECK.validate_artifact(malformed, "fixture"))

    def test_measured_date_requires_a_real_iso_calendar_date(self) -> None:
        for date in ("not-a-date", "2026-02-30", "20260101", 20260101):
            value = profile()
            value["provenance"]["kind"] = "measured"
            value["provenance"]["measurement"] = {"date": date}
            self.assertIn("valid ISO date", " ".join(CHECK.validate(value, "fixture")))

    def test_nonfinite_values_are_rejected_at_every_depth(self) -> None:
        for number in (float("nan"), float("inf"), float("-inf")):
            value = profile()
            value["reference_conditions"] = {"temperature_c": number}
            self.assertIn("finite", " ".join(CHECK.validate(value, "fixture")))
            value = profile()
            value["photometric"]["channels"][0]["response"] = [{"light": number}]
            self.assertIn("finite", " ".join(CHECK.validate(value, "fixture")))

    def test_published_sensitivity_table_matches_generated_values(self) -> None:
        tool = TOOL.with_name("generate_intensity_sensitivity.py")
        spec = importlib.util.spec_from_file_location("sensitivity", tool)
        assert spec and spec.loader
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        report = (tool.parent.parent / "measured-profiles" / "P1-CHARACTERIZATION.md").read_text()
        for row in generator.data()["rows"]:
            values = row["max_min"]
            expected = f'| {row["part"]} | {values["uncorrected"]:.2f} | {values["typical_led_strip"]:.2f} | {values["typical_8mm_pixel"]:.2f} | 1.00 |'
            self.assertIn(expected, report)

    def test_incomplete_datasheet_record_is_valid_but_not_runtime_admissible(self) -> None:
        self.assertEqual(CHECK.validate(profile(), "fixture"), [])

    def test_empty_channels_and_empty_sources_are_rejected(self) -> None:
        value = profile()
        value["photometric"]["channels"] = []
        value["provenance"]["source_documents"] = []
        errors = " ".join(CHECK.validate(value, "fixture"))
        self.assertIn("photometric.channels must not be empty", errors)
        self.assertIn("source_documents must not be empty", errors)

    def test_observations_are_typed_and_have_full_citations(self) -> None:
        value = profile()
        value["photometric"]["channels"][0]["dominant_wavelength_nm"] = {
            "value": "620", "unit": "nm", "qualifier": "typical",
            "source": {"path": "x.pdf", "page": 0},
        }
        errors = " ".join(CHECK.validate(value, "fixture"))
        self.assertIn("observation.value must be a finite number", errors)
        self.assertIn("observation source requires positive page and section", errors)

    def test_measured_profile_requires_instrument_uncertainty_serial_and_bin(self) -> None:
        value = profile()
        value["provenance"]["kind"] = "measured"
        value["provenance"]["measurement"] = {"instrument": {"model": "x"}, "date": "2026-01-01", "fixture_geometry": "x", "temperature_c": 25, "drive_conditions": "x", "raw_data_pointer": "x"}
        errors = " ".join(CHECK.validate(value, "fixture"))
        self.assertIn("instrument.serial", errors)
        self.assertIn("instrument.xy_uncertainty", errors)
        self.assertIn("measurement.bin_or_lot", errors)

    def test_schema_rejects_unknown_observation_shape(self) -> None:
        schema = json.loads((Path(__file__).parents[1] / "measured-profiles" / "schema-v1.json").read_text())
        value = profile()
        value["photometric"]["channels"][0]["dominant_wavelength_nm"] = {"arbitrary": "ghost"}
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))

    def test_checked_in_artifact_is_json_schema_valid(self) -> None:
        schema = json.loads((Path(__file__).parents[1] / "measured-profiles" / "schema-v1.json").read_text())
        artifacts = sorted((Path(__file__).parents[1] / "measured-profiles").glob("*.profile.json"))
        self.assertGreaterEqual(len(artifacts), 2)
        for path in artifacts:
            with self.subTest(path=path.name):
                artifact = json.loads(path.read_text())
                self.assertEqual(list(Draft202012Validator(schema).iter_errors(artifact)), [])

    def test_ws2816_combined_white_is_not_a_diode_chromaticity(self) -> None:
        artifact_path = Path(__file__).parents[1] / "measured-profiles" / "ws2816b-2121-none-datasheet-r1.profile.json"
        artifact = json.loads(artifact_path.read_text())
        photometric = artifact["photometric"]
        self.assertIn("full_drive_white_chromaticity", photometric)
        self.assertTrue(all("chromaticity" not in channel for channel in photometric["channels"]))
        self.assertEqual(photometric["channels"][0]["dominant_wavelength_nm_range"]["min"]["value"], 620)
        self.assertEqual(set(photometric["channels"][0]["luminous_intensity_mcd_range"]), {"min", "typical", "max"})
        self.assertEqual(CHECK.validate_artifact(artifact, artifact_path.name), [])

    def test_duplicate_profile_id_is_rejected(self) -> None:
        self.assertIn("duplicate append-only profile_id", " ".join(CHECK.validate_registry([(profile(), "one"), (profile(), "two")])))

    def test_identity_is_append_only_canonical_id(self) -> None:
        value = profile()
        value["profile_id"] = "ws2812b/5050/none/other-r2"
        self.assertIn("identity does not reproduce profile_id", " ".join(CHECK.validate(value, "fixture")))

    def test_measured_profile_requires_reproducibility_fields(self) -> None:
        value = profile()
        value["provenance"]["kind"] = "measured"
        self.assertIn("measurement.instrument", " ".join(CHECK.validate(value, "fixture")))

    def test_unknown_five_bit_semantics_is_rejected(self) -> None:
        value = profile()
        value["chip_encoding"]["five_bit_semantics"] = "global_current"
        self.assertIn("invalid five_bit_semantics", " ".join(CHECK.validate(value, "fixture")))

    def test_checked_in_artifact_passes_invariant_checks(self) -> None:
        artifact = Path(__file__).parents[1] / "measured-profiles" / "ws2812b-5050-none-datasheet-r1.profile.json"
        self.assertEqual(CHECK.validate(json.loads(artifact.read_text()), artifact.name), [])
