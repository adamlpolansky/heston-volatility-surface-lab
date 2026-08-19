"""Small numerical helpers."""

from __future__ import annotations

import math


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide two numbers and return `default` when the denominator is tiny."""

    if abs(denominator) < 1e-15:
        return default
    return numerator / denominator


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a float to an inclusive interval."""

    return min(max(value, lower), upper)


def normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""

    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_pdf(x: float) -> float:
    """Standard normal probability density function."""

    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
