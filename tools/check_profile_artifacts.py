"""Validate the dependency-free invariants of profile artifacts.

Use ``uv run python tools/check_profile_artifacts.py``.  JSON Schema is
checked separately by consumers that have a JSON Schema implementation; these
explicit checks keep the registry usable in the minimal CI environment.
"""

import json
import math
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "measured-profiles"
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")
QUALIFIERS = {"min", "typical", "max", "measured", "inferred"}
FIVE_BIT = {"secondary_slow_pwm", "current_gain", "unknown", "not_applicable"}
OBSERVATION_FIELDS = {"dominant_wavelength_nm", "luminous_intensity_mcd", "relative_y", "forward_voltage_v", "current_ma", "idle_power"}


def _validate_observation(observation: object, name: str, errors: list[str]) -> None:
    if not isinstance(observation, dict) or not isinstance(observation.get("value"), (int, float)) or isinstance(observation.get("value"), bool) or not math.isfinite(observation["value"]):
        errors.append(f"{name}: observation.value must be a finite number")
    if isinstance(observation, dict) and observation.get("qualifier") not in QUALIFIERS:
        errors.append(f"{name}: invalid observation qualifier")
    source = observation.get("source") if isinstance(observation, dict) else None
    if not isinstance(source, dict) or not isinstance(source.get("path"), str) or not source["path"] or not isinstance(source.get("page"), int) or source["page"] < 1 or not isinstance(source.get("section"), str) or not source["section"]:
        errors.append(f"{name}: observation source requires positive page and section")


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
    if not provenance.get("source_documents"):
        errors.append(f"{name}: source_documents must not be empty")
    if provenance.get("kind") == "measured":
        measurement = provenance.get("measurement", {})
        for key in ("instrument", "date", "fixture_geometry", "temperature_c", "drive_conditions", "raw_data_pointer"):
            if key not in measurement:
                errors.append(f"{name}: measured profile missing measurement.{key}")
        instrument = measurement.get("instrument", {})
        for key in ("serial", "xy_uncertainty"):
            if key not in instrument:
                errors.append(f"{name}: measured profile missing instrument.{key}")
        if "bin_or_lot" not in measurement:
            errors.append(f"{name}: measured profile missing measurement.bin_or_lot")
    if profile["chip_encoding"].get("five_bit_semantics") not in FIVE_BIT:
        errors.append(f"{name}: invalid five_bit_semantics")
    channels = profile["photometric"].get("channels", [])
    if not channels:
        errors.append(f"{name}: photometric.channels must not be empty")
    for channel in channels:
        for key in OBSERVATION_FIELDS - {"forward_voltage_v", "current_ma", "idle_power"}:
            if key in channel:
                _validate_observation(channel[key], name, errors)
        for observation in (channel.get("relative_y"), *(channel.get("chromaticity") or {}).values()):
            if observation is not None:
                _validate_observation(observation, name, errors)
    for channel in profile["electrical"].get("channels", []):
        for key in ("forward_voltage_v", "current_ma"):
            if key in channel:
                _validate_observation(channel[key], name, errors)
    if "idle_power" in profile["electrical"]:
        _validate_observation(profile["electrical"]["idle_power"], name, errors)
    return errors


def validate_registry(profiles: list[tuple[dict, str]]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    for profile, name in profiles:
        errors.extend(validate(profile, name))
        profile_id = profile.get("profile_id")
        if profile_id in ids:
            errors.append(f"{name}: duplicate append-only profile_id {profile_id}")
        ids.add(profile_id)
    return errors


def main() -> int:
    profiles = [(json.loads(path.read_text()), path.name) for path in sorted(PROFILES.glob("*.profile.json"))]
    errors = validate_registry(profiles)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("profile artifact checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
