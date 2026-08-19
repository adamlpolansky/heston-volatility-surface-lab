from __future__ import annotations

from datetime import date

import pandas as pd

from heston_arb_lab.signals.parity import scan_put_call_parity
from heston_arb_lab.signals.ranking import rank_signals
from heston_arb_lab.surface.surface_builder import (
    SurfaceBuildConfig,
    build_surface,
    synthetic_option_chain,
)


def test_parity_signal_and_ranking() -> None:
    asof = date(2025, 1, 15)
    quotes = synthetic_option_chain(asof=asof)
    first_expiry = quotes["expiration"].min()
    mask = (
        (quotes["expiration"] == first_expiry)
        & (quotes["strike"] == 100.0)
        & (quotes["right"] == "call")
    )
    quotes.loc[mask, ["bid", "ask"]] = quotes.loc[mask, ["bid", "ask"]] + 0.50
    surface = build_surface(quotes, SurfaceBuildConfig(spot=100.0, asof=asof, rate=0.04))
    signals = scan_put_call_parity(surface, spot=100.0, rate=0.04, min_abs_residual=0.01)
    ranked = rank_signals(signals, min_net_edge=-10_000.0)
    assert signals
    assert isinstance(ranked, pd.DataFrame)
    assert ranked.iloc[0]["signal_type"] == "put_call_parity"
    assert "estimated_cost" in ranked.columns
