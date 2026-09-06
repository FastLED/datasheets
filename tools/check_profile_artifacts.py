"""Validate the dependency-free invariants of profile artifacts.

Use ``uv run python tools/check_profile_artifacts.py``.  JSON Schema is
checked separately by consumers that have a JSON Schema implementation; these
explicit checks keep the registry usable in the minimal CI environment.
"""

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "measured-profiles"
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")
QUALIFIERS = {"min", "typical", "max", "measured", "inferred"}
FIVE_BIT = {"secondary_slow_pwm", "current_gain", "unknown", "not_applicable"}


def validate(profile: dict, name: str) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "profile_id", "identity", "provenance", "photometric", "electrical", "chip_encoding"):
        if key not in profile:
            errors.append(f"{name}: missing {key}")
    if errors:
        return errors
    if profile["schema_version"] != "1.0":
        errors.append(f"{name}: unsupported schema_version")
    if not ID.fullmatch(profile["profile_id"]):
        errors.append(f"{name}: invalid profile_id")
    identity = profile["identity"]
    expected = "/".join(str(identity.get(k, "")) for k in ("part", "package_variant", "w_channel_variant", "report_id"))
    if expected != profile["profile_id"]:
        errors.append(f"{name}: identity does not reproduce profile_id")
    provenance = profile["provenance"]
    if provenance.get("kind") not in {"datasheet_derived", "measured"}:
        errors.append(f"{name}: invalid provenance kind")
    if provenance.get("report_id") != identity.get("report_id"):
        errors.append(f"{name}: report ID must match identity")
    if provenance.get("kind") == "measured":
        measurement = provenance.get("measurement", {})
        for key in ("instrument", "date", "fixture_geometry", "temperature_c", "drive_conditions", "raw_data_pointer"):
            if key not in measurement:
                errors.append(f"{name}: measured profile missing measurement.{key}")
    if profile["chip_encoding"].get("five_bit_semantics") not in FIVE_BIT:
        errors.append(f"{name}: invalid five_bit_semantics")
    for channel in profile["photometric"].get("channels", []):
        for observation in (channel.get("relative_y"), *(channel.get("chromaticity") or {}).values()):
            if observation is not None and observation.get("qualifier") not in QUALIFIERS:
                errors.append(f"{name}: invalid observation qualifier")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in sorted(PROFILES.glob("*.profile.json")):
        errors.extend(validate(json.loads(path.read_text()), path.name))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("profile artifact checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
