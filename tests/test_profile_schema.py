import importlib.util
import json
import unittest
from pathlib import Path


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
        "photometric": {"channels": [{"name": "red"}]}, "electrical": {},
        "chip_encoding": {"five_bit_semantics": "not_applicable"},
    }


class ProfileSchemaTest(unittest.TestCase):
    def test_minimal_datasheet_profile_is_valid(self) -> None:
        self.assertEqual(CHECK.validate(profile(), "fixture"), [])

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
