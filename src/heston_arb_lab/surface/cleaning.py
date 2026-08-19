"""Surface input normalization and quote cleaning."""

from __future__ import annotations

import pandas as pd

from heston_arb_lab.data.quality import add_quote_quality_flags, filter_liquid_quotes
from heston_arb_lab.utils.validation import require_columns


def normalize_option_chain(quotes: pd.DataFrame) -> pd.DataFrame:
    """Normalize vendor-like quote columns to internal names."""

    frame = quotes.copy()
    frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
    rename_map = {"root": "symbol", "option_type": "right", "expiry": "expiration"}
    frame = frame.rename(
        columns={key: value for key, value in rename_map.items() if key in frame.columns}
    )
    if "right" in frame.columns:
        frame["right"] = frame["right"].astype(str).str.lower().replace({"c": "call", "p": "put"})
    return frame


def clean_option_quotes(
    quotes: pd.DataFrame,
    *,
    max_relative_spread: float = 0.5,
    min_mid: float = 0.01,
) -> pd.DataFrame:
    """Normalize, flag, and drop quotes failing basic quality checks."""

    frame = normalize_option_chain(quotes)
    require_columns(
        frame, ["symbol", "expiration", "strike", "right", "bid", "ask"], "option quotes"
    )
    return filter_liquid_quotes(
        frame,
        max_relative_spread=max_relative_spread,
        min_mid=min_mid,
    )


def with_quality_flags(quotes: pd.DataFrame) -> pd.DataFrame:
    """Return normalized quotes with quality flags retained."""

    return add_quote_quality_flags(normalize_option_chain(quotes))
