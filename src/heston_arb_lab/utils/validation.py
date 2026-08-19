"""Validation helpers for dataframe-like inputs."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def require_columns(frame: pd.DataFrame, required: Iterable[str], name: str = "dataframe") -> None:
    """Raise a clear error when a dataframe is missing required columns."""

    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(missing)}")
