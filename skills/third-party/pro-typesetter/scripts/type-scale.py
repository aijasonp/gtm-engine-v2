#!/usr/bin/env python3
"""Type scale generator for the pro-typesetter skill.

Example CLI usage::

    python3 type-scale.py --base 11 --ratio perfect-fourth --steps 6 --down 1

Can also be imported::

    from type_scale import generate_scale
"""

from __future__ import annotations

import argparse
from typing import Dict, Iterable, List, Tuple

RATIO_PRESETS = {
    "major-second": (1.125, "Major Second"),
    "major-third": (1.25, "Major Third"),
    "perfect-fourth": (1.333, "Perfect Fourth"),
    "golden": (1.618, "Golden Ratio"),
}

DEFAULT_RATIO = RATIO_PRESETS["perfect-fourth"][0]
DEFAULT_RATIO_LABEL = RATIO_PRESETS["perfect-fourth"][1]
LARGE_STEP_NAMES = [
    "Display",
    "H1",
    "H2",
    "H3",
    "H4/Subhead",
]
SMALL_STEP_NAMES = [
    "Caption",
]


def _resolve_ratio(value: str | None) -> Tuple[float, str]:
    if value is None:
        return DEFAULT_RATIO, DEFAULT_RATIO_LABEL
    key = value.lower()
    if key in RATIO_PRESETS:
        return RATIO_PRESETS[key]
    try:
        numeric = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid ratio '{value}'. Use a numeric value or one of: {', '.join(RATIO_PRESETS)}"
        ) from exc

    for preset_value, preset_label in RATIO_PRESETS.values():
        if abs(numeric - preset_value) < 1e-6:
            return preset_value, preset_label
    return numeric, f"Custom ({numeric:.3f})"


def _line_height_and_tracking(size: float, base: float, ratio: float) -> Tuple[float, int]:
    rel = size / base
    if rel > ratio ** 4:
        return 1.1, -20
    if rel > ratio ** 3:
        return 1.1, -15
    if rel > ratio ** 2:
        return 1.2, -10
    if rel > ratio ** 1.3:
        return 1.3, -5
    if rel >= 1:
        return 1.35, 0
    if rel >= ratio ** -0.5:
        return 1.4, 0
    return 1.4, 10


def generate_scale(
    base: float = 11.0,
    ratio: float = DEFAULT_RATIO,
    steps: int = 5,
    down: int = 1,
    unit: str = "pt",
) -> List[Dict[str, float | int | str]]:
    if base <= 0:
        raise ValueError("Base size must be positive")
    if ratio <= 0:
        raise ValueError("Ratio must be positive")
    if steps < 0 or down < 0:
        raise ValueError("Steps and down values must be non-negative")

    scale: List[Dict[str, float | int | str]] = []

    positive_exponents = list(range(steps, 0, -1))
    for idx, exponent in enumerate(positive_exponents):
        name = (
            LARGE_STEP_NAMES[idx]
            if idx < len(LARGE_STEP_NAMES)
            else f"Level +{idx - len(LARGE_STEP_NAMES) + 1}"
        )
        size = base * (ratio ** exponent)
        line_height, tracking = _line_height_and_tracking(size, base, ratio)
        scale.append(
            {
                "name": name,
                "size": size,
                "unit": unit,
                "line_height": line_height,
                "tracking": tracking,
            }
        )

    # Base
    # Body (base) gets a more generous line height for readability
    scale.append(
        {
            "name": "Body",
            "size": base,
            "unit": unit,
            "line_height": 1.5,
            "tracking": 0,
        }
    )

    for idx in range(down):
        exponent = idx + 1
        name = (
            SMALL_STEP_NAMES[idx]
            if idx < len(SMALL_STEP_NAMES)
            else f"Level -{exponent}"
        )
        size = base / (ratio ** exponent)
        line_height, tracking = _line_height_and_tracking(size, base, ratio)
        scale.append(
            {
                "name": name,
                "size": size,
                "unit": unit,
                "line_height": line_height,
                "tracking": tracking,
            }
        )

    return scale


def _format_scale(scale: Iterable[Dict[str, float | int | str]]) -> str:
    rows = []
    for entry in scale:
        size = float(entry["size"])
        unit = entry["unit"]
        rows.append(
            f"{entry['name']:<10} {size:>5.1f}{unit:<3}   lh: {entry['line_height']:<3.2f}   tracking: {entry['tracking']:>+4}"
        )
    return "\n".join(rows)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a typography scale table")
    parser.add_argument("--base", type=float, default=11.0, help="Base font size (default: 11)")
    parser.add_argument("--ratio", type=str, default="perfect-fourth", help="Scale ratio or named preset")
    parser.add_argument("--steps", type=int, default=5, help="Number of steps above the base")
    parser.add_argument("--down", type=int, default=1, help="Number of steps below the base")
    parser.add_argument("--unit", choices=("pt", "px"), default="pt", help="Unit for output sizes")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> None:
    args = parse_args(argv)
    ratio_value, ratio_label = _resolve_ratio(args.ratio)
    scale = generate_scale(
        base=args.base,
        ratio=ratio_value,
        steps=args.steps,
        down=args.down,
        unit=args.unit,
    )
    header = f"Type Scale — Base: {args.base:g}{args.unit} | Ratio: {ratio_value:.3f} ({ratio_label})"
    divider = "\u2500" * len(header)
    print(header)
    print(divider)
    print(_format_scale(scale))


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
