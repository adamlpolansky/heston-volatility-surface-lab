from __future__ import annotations

import pandas as pd

from heston_arb_lab.data.quality import add_quote_quality_flags
from heston_arb_lab.surface.no_arbitrage import run_no_arbitrage_checks


def test_synthetic_clean_surface_has_no_violations(synthetic_surface: pd.DataFrame) -> None:
    violations = run_no_arbitrage_checks(synthetic_surface, rate=0.04, tolerance=1e-5)
    assert violations.empty


def test_broken_call_monotonicity_is_detected(synthetic_surface: pd.DataFrame) -> None:
    broken = synthetic_surface.copy()
    first_expiry = broken["expiration"].min()
    mask = (
        (broken["expiration"] == first_expiry)
        & (broken["right"] == "call")
        & (broken["strike"] == 105.0)
    )
    broken.loc[mask, "mid"] = (
        broken.loc[
            (broken["expiration"] == first_expiry)
            & (broken["right"] == "call")
            & (broken["strike"] == 100.0),
            "mid",
        ].iloc[0]
        + 1.0
    )
    violations = run_no_arbitrage_checks(broken, rate=0.04)
    assert "strike_monotonicity" in set(violations["violation_type"])


def test_quote_quality_flags_detect_bad_markets() -> None:
    quotes = pd.DataFrame(
        {
            "bid": [1.2, -1.0, 1.0, 0.0],
            "ask": [1.0, 1.2, 10.0, 0.0],
        }
    )
    flagged = add_quote_quality_flags(quotes, max_relative_spread=0.5, min_mid=0.01)
    assert flagged.loc[0, "crossed_market"]
    assert flagged.loc[1, "negative_quote"]
    assert flagged.loc[2, "wide_spread"]
    assert flagged.loc[3, "tiny_mid"]
