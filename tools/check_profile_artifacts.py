"""Validate profile artifacts with both schema and semantic invariants.

Use ``uv run --with jsonschema python tools/check_profile_artifacts.py``.
Admission consumers must use validate_artifact, not the invariant-only helper.
"""

import json
import math
import re
import sys
from datetime import date
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


def _finite_errors(value: object, path: str) -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{path}: numeric values must be finite"]
    if isinstance(value, dict):
        return [error for key, child in value.items()
                for error in _finite_errors(child, f"{path}.{key}")]
    if isinstance(value, list):
        return [error for index, child in enumerate(value)
                for error in _finite_errors(child, f"{path}[{index}]")]
    return []


def validate(profile: dict, name: str) -> list[str]:
    finite_errors = _finite_errors(profile, name)
    if finite_errors:
        return finite_errors
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
        observed_date = measurement.get("date")
        try:
            if not isinstance(observed_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed_date):
                raise ValueError("invalid ISO date shape")
            date.fromisoformat(observed_date)
        except ValueError:
            errors.append(f"{name}: measurement.date must be a valid ISO date")
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


def validate_artifact(profile: object, name: str) -> list[str]:
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads((PROFILES / "schema-v1.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = _finite_errors(profile, name)
    errors.extend(f"{name}: {error.message}" for error in validator.iter_errors(profile))
    if errors:
        return errors
    errors = validate(profile, name)
    if profile.get("runtime_admissible", False):
        expected = {
            "rgb": {"red", "green", "blue"},
            "rgbw": {"red", "green", "blue", "white"},
            "rgbww": {"red", "green", "blue", "warm_white", "cool_white"},
        }.get(profile.get("topology"))
        channels = profile["photometric"]["channels"]
        actual = {channel["name"] for channel in channels}
        if expected is None or actual != expected or len(channels) != len(actual) or not all(channel["runtime_admissible"] for channel in channels):
            errors.append(f"{name}: runtime admission requires a complete declared channel set with usable xy/Y")
    return errors


def validate_registry(profiles: list[tuple[dict, str]]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    for profile, name in profiles:
        errors.extend(validate_artifact(profile, name))
        profile_id = profile.get("profile_id") if isinstance(profile, dict) else None
        if not isinstance(profile_id, str):
            continue
        if profile_id in ids:
            errors.append(f"{name}: duplicate append-only profile_id {profile_id}")
        ids.add(profile_id)
    return errors


def parse_artifact(text: str) -> object:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-JSON numeric constant: {value}")

    return json.loads(text, parse_constant=reject_constant)


def main() -> int:
    profiles = []
    for path in sorted(PROFILES.glob("*.profile.json")):
        try:
            profiles.append((parse_artifact(path.read_text()), path.name))
        except ValueError as error:
            print(f"{path.name}: {error}", file=sys.stderr)
            return 1
    errors = validate_registry(profiles)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("profile artifact checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
