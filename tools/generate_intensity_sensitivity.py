"""Generate the explicitly non-colorimetric legacy-correction sensitivity table."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "measured-profiles" / "intensity-sensitivity-v1.json"
ROWS = {
    "SK6812 midpoint": (850, 1850, 850), "WS2812B midpoint": (405, 690, 190),
    "WS2813A": (480, 1500, 320), "WS2813B / WS2815 central": (360, 1150, 220),
    "WS2813C": (120, 540, 130), "WS2813D": (100, 420, 110),
    "GS8208 LED5050 option": (450, 1300, 280),
}
MODELS = {"uncorrected": (1, 1, 1), "typical_led_strip": (1, 176 / 255, 240 / 255), "typical_8mm_pixel": (1, 224 / 255, 140 / 255)}


def ratio(intensities: tuple[float, float, float], correction: tuple[float, float, float]) -> float:
    corrected = [value * scale for value, scale in zip(intensities, correction)]
    return round(max(corrected) / min(corrected), 2)


def data() -> dict:
    return {"kind": "photopic_intensity_neutral_sensitivity_not_color_accuracy", "models": {key: list(value) for key, value in MODELS.items()}, "rows": [{"part": name, "intensity_mcd": list(values), "max_min": {key: ratio(values, model) for key, model in MODELS.items()}} for name, values in ROWS.items()]}


def main() -> int:
    rendered = json.dumps(data(), indent=2) + "\n"
    if sys.argv[1:] == ["--check"]:
        return 0 if OUTPUT.read_text() == rendered else 1
    OUTPUT.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
