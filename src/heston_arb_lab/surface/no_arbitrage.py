"""No-arbitrage diagnostics for cleaned option surfaces."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _record(
    violations: list[dict[str, Any]],
    violation_type: str,
    group_key: dict[str, Any],
    severity: float,
    message: str,
) -> None:
    violations.append(
        {
            "violation_type": violation_type,
            "severity": float(severity),
            "message": message,
            **group_key,
        }
    )


def check_strike_monotonicity(
    surface: pd.DataFrame, price_col: str = "mid", tolerance: float = 1e-8
) -> pd.DataFrame:
    """Check call/put monotonicity across strikes."""

    violations: list[dict[str, Any]] = []
    for keys, group in surface.groupby(["symbol", "expiration", "right"]):
        symbol, expiration, right = keys
        ordered = group.sort_values("strike")
        diffs = ordered[price_col].diff()
        bad = diffs > tolerance if right == "call" else diffs < -tolerance
        for idx in ordered.loc[bad.fillna(False)].index:
            _record(
                violations,
                "strike_monotonicity",
                {"symbol": symbol, "expiration": expiration, "right": right, "row_index": idx},
                abs(float(diffs.loc[idx])),
                f"{right} price monotonicity failed at row {idx}",
            )
    return pd.DataFrame(violations)


def check_vertical_bounds(
    surface: pd.DataFrame,
    *,
    rate: float = 0.0,
    price_col: str = "mid",
    tolerance: float = 1e-8,
) -> pd.DataFrame:
    """Check vertical spread lower/upper bounds."""

    violations: list[dict[str, Any]] = []
    for keys, group in surface.groupby(["symbol", "expiration", "right"]):
        symbol, expiration, right = keys
        ordered = group.sort_values("strike").reset_index()
        for left, right_row in zip(
            ordered.itertuples(), ordered.iloc[1:].itertuples(), strict=False
        ):
            maturity = float(getattr(left, "time_to_expiry", 0.0))
            discount = math.exp(-rate * maturity)
            width = (float(right_row.strike) - float(left.strike)) * discount
            left_price = float(getattr(left, price_col))
            right_price = float(getattr(right_row, price_col))
            spread = left_price - right_price if right == "call" else right_price - left_price
            if spread < -tolerance or spread > width + tolerance:
                _record(
                    violations,
                    "vertical_bounds",
                    {
                        "symbol": symbol,
                        "expiration": expiration,
                        "right": right,
                        "lower_strike": float(left.strike),
                        "upper_strike": float(right_row.strike),
                    },
                    min(abs(spread), abs(spread - width)),
                    "vertical spread outside no-arbitrage bounds",
                )
    return pd.DataFrame(violations)


def check_butterfly_convexity(
    surface: pd.DataFrame, price_col: str = "mid", tolerance: float = 1e-8
) -> pd.DataFrame:
    """Check discrete convexity of option prices in strike."""

    violations: list[dict[str, Any]] = []
    for keys, group in surface.groupby(["symbol", "expiration", "right"]):
        symbol, expiration, right = keys
        ordered = group.sort_values("strike").reset_index(drop=True)
        for idx in range(1, len(ordered) - 1):
            k0, k1, k2 = ordered.loc[idx - 1 : idx + 1, "strike"].astype(float).to_list()
            p0, p1, p2 = ordered.loc[idx - 1 : idx + 1, price_col].astype(float).to_list()
            left_slope = (p1 - p0) / (k1 - k0)
            right_slope = (p2 - p1) / (k2 - k1)
            if right_slope + tolerance < left_slope:
                _record(
                    violations,
                    "butterfly_convexity",
                    {
                        "symbol": symbol,
                        "expiration": expiration,
                        "right": right,
                        "center_strike": k1,
                    },
                    left_slope - right_slope,
                    "price curve is locally concave in strike",
                )
    return pd.DataFrame(violations)


def check_calendar_total_variance(surface: pd.DataFrame, tolerance: float = 1e-8) -> pd.DataFrame:
    """Check total variance is non-decreasing across expiries at matching strikes."""

    violations: list[dict[str, Any]] = []
    if "total_variance" not in surface.columns:
        return pd.DataFrame(violations)
    for keys, group in surface.groupby(["symbol", "right", "strike"]):
        symbol, right, strike = keys
        ordered = group.sort_values("time_to_expiry")
        diffs = ordered["total_variance"].diff()
        for idx in ordered.loc[diffs < -tolerance].index:
            _record(
                violations,
                "calendar_total_variance",
                {"symbol": symbol, "right": right, "strike": float(strike), "row_index": idx},
                abs(float(diffs.loc[idx])),
                "total variance decreased with maturity",
            )
    return pd.DataFrame(violations)


def run_no_arbitrage_checks(
    surface: pd.DataFrame,
    *,
    rate: float = 0.0,
    price_col: str = "mid",
    tolerance: float = 1e-8,
) -> pd.DataFrame:
    """Run all available no-arbitrage diagnostics."""

    checks = [
        check_strike_monotonicity(surface, price_col, tolerance),
        check_vertical_bounds(surface, rate=rate, price_col=price_col, tolerance=tolerance),
        check_butterfly_convexity(surface, price_col, tolerance),
        check_calendar_total_variance(surface, tolerance),
    ]
    non_empty = [check for check in checks if not check.empty]
    if not non_empty:
        return pd.DataFrame(columns=["violation_type", "severity", "message"])
    return pd.concat(non_empty, ignore_index=True)
