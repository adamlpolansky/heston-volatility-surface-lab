"""Quote quality flags and filters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from heston_arb_lab.utils.validation import require_columns


def add_quote_quality_flags(
    quotes: pd.DataFrame,
    *,
    max_relative_spread: float = 0.5,
    min_mid: float = 0.01,
    max_age_seconds: float | None = None,
    asof: datetime | None = None,
) -> pd.DataFrame:
    """Add bid/ask quality flags without dropping rows."""

    require_columns(quotes, ["bid", "ask"], "quotes")
    frame = quotes.copy()
    frame["mid"] = (frame["bid"] + frame["ask"]) / 2.0
    frame["spread"] = frame["ask"] - frame["bid"]
    frame["relative_spread"] = np.where(frame["mid"] > 0, frame["spread"] / frame["mid"], np.inf)
    frame["crossed_market"] = frame["bid"] > frame["ask"]
    frame["negative_quote"] = (frame["bid"] < 0) | (frame["ask"] < 0)
    frame["missing_quote"] = frame[["bid", "ask"]].isna().any(axis=1)
    frame["tiny_mid"] = frame["mid"] < min_mid
    frame["wide_spread"] = frame["relative_spread"] > max_relative_spread

    if max_age_seconds is not None and "timestamp" in frame.columns:
        reference = asof or datetime.now(tz=UTC)
        timestamps = pd.to_datetime(frame["timestamp"], utc=True)
        age = (pd.Timestamp(reference) - timestamps).dt.total_seconds()
        frame["stale_quote"] = age > max_age_seconds
    else:
        frame["stale_quote"] = False

    frame["quality_reject"] = frame[
        [
            "crossed_market",
            "negative_quote",
            "missing_quote",
            "tiny_mid",
            "wide_spread",
            "stale_quote",
        ]
    ].any(axis=1)
    return frame


def filter_liquid_quotes(quotes: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    """Return quotes that pass basic conservative quality checks."""

    flagged = add_quote_quality_flags(quotes, **kwargs)
    return flagged.loc[~flagged["quality_reject"]].copy()
