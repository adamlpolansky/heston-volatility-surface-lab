"""Simple interpolation utilities for surface visualization."""

from __future__ import annotations

import pandas as pd


def build_iv_grid(surface: pd.DataFrame) -> pd.DataFrame:
    """Pivot a surface into an expiry-by-log-moneyness IV grid."""

    return surface.pivot_table(
        index="time_to_expiry",
        columns="log_moneyness",
        values="implied_vol",
        aggfunc="mean",
    ).sort_index()


def interpolate_missing(grid: pd.DataFrame) -> pd.DataFrame:
    """Interpolate missing grid points along both dimensions."""

    return grid.interpolate(axis=1, limit_direction="both").interpolate(
        axis=0, limit_direction="both"
    )
