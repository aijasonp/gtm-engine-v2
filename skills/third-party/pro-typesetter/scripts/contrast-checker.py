#!/usr/bin/env python3
"""WCAG contrast ratio utility for the pro-typesetter skill.

Can be used as a CLI or imported as a module::

    python3 contrast-checker.py #1F4E79 #FFFFFF
    from contrast_checker import contrast_ratio

The script accepts hexadecimal colors (3- or 6-digit, with or without the leading
``#``) as well as CSS ``rgb(r,g,b)`` strings.
"""

from __future__ import annotations

import re
import sys
from typing import Iterable, Tuple

_RGB_REGEX = re.compile(r"rgb\((\d{1,3}),(\d{1,3}),(\d{1,3})\)$", re.IGNORECASE)


def _expand_shorthand(hex_code: str) -> str:
    """Expand 3-digit shorthand hex colors to 6-digit form."""
    if len(hex_code) == 3:
        return "".join(ch * 2 for ch in hex_code)
    return hex_code


def _parse_hex(color: str) -> Tuple[int, int, int]:
    color = color.lstrip("#").lower()
    if len(color) not in (3, 6) or not all(c in "0123456789abcdef" for c in color):
        raise ValueError(f"Invalid hex color: {color}")
    color = _expand_shorthand(color)
    return tuple(int(color[i : i + 2], 16) for i in range(0, 6, 2))  # type: ignore[return-value]


def _parse_rgb(color: str) -> Tuple[int, int, int]:
    match = _RGB_REGEX.match(color.replace(" ", ""))
    if not match:
        raise ValueError(f"Invalid rgb() color: {color}")
    r, g, b = (int(value) for value in match.groups())
    if not all(0 <= channel <= 255 for channel in (r, g, b)):
        raise ValueError(f"RGB values must be between 0 and 255: {color}")
    return r, g, b


def parse_color(color: str) -> Tuple[int, int, int]:
    """Parse a color string into an (R, G, B) tuple of ints 0-255."""
    color = color.strip()
    if color.lower().startswith("rgb"):
        return _parse_rgb(color)
    return _parse_hex(color)


def _channel_to_linear(channel: float) -> float:
    """Convert an sRGB channel (0-1) to its linear-light value."""
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(color: Iterable[int]) -> float:
    """Compute the WCAG relative luminance of an RGB color."""
    r, g, b = (component / 255.0 for component in color)
    r_lin, g_lin, b_lin = map(_channel_to_linear, (r, g, b))
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(color_a: Iterable[int], color_b: Iterable[int]) -> float:
    """Return the WCAG contrast ratio between two colors."""
    lum_a = relative_luminance(color_a)
    lum_b = relative_luminance(color_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


_THRESHOLDS = {
    "WCAG AA Body": 4.5,
    "WCAG AA Large": 3.0,
    "WCAG AAA Body": 7.0,
    "WCAG AAA Large": 4.5,
}


def _format_pass(value: float, threshold: float) -> Tuple[str, str]:
    passes = value >= threshold
    icon = "✅" if passes else "❌"
    return icon, f"{icon} {'Pass' if passes else 'Fail'} ({value:.2f} vs {threshold})"


def _summary_line(label: str, passes: bool) -> str:
    icon = "✅" if passes else "❌"
    return f"{icon} {label}"


def _run_cli(color1: str, color2: str) -> None:
    rgb1 = parse_color(color1)
    rgb2 = parse_color(color2)
    ratio = contrast_ratio(rgb1, rgb2)

    print(f"Contrast ratio: {ratio:.2f}:1")
    results = {}
    for label, threshold in _THRESHOLDS.items():
        passes = ratio >= threshold
        icon = "✅" if passes else "❌"
        print(f"{label}: {icon} (threshold {threshold}:1)")
        results[label] = passes

    # Summary lines (stripped labels for readability)
    print(_summary_line("AA Body", results["WCAG AA Body"]))
    print(_summary_line("AA Large", results["WCAG AA Large"]))
    print(_summary_line("AAA Body", results["WCAG AAA Body"]))
    print(_summary_line("AAA Large", results["WCAG AAA Large"]))


def main(argv: Iterable[str]) -> None:
    args = list(argv)
    if len(args) != 2:
        raise SystemExit("Usage: python3 contrast-checker.py <color1> <color2>")
    try:
        _run_cli(args[0], args[1])
    except ValueError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main(sys.argv[1:])
