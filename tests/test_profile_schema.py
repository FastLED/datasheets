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
        artifact = json.loads((Path(__file__).parents[1] / "measured-profiles" / "ws2812b-5050-none-datasheet-r1.profile.json").read_text())
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(artifact)), [])

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
