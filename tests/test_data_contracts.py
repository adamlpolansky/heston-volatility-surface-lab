from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from heston_arb_lab.data.schemas import OptionQuote, UnderlyingBar
from heston_arb_lab.data.storage import ensure_data_dirs


def test_option_quote_contract_validates() -> None:
    quote = OptionQuote(
        symbol="SYNTH",
        expiration=date(2025, 1, 17),
        strike=100.0,
        right="call",
        timestamp=datetime(2025, 1, 15, 15, 30),
        bid=1.0,
        ask=1.1,
        bid_size=10,
        ask_size=12,
    )
    assert quote.strike == 100.0


def test_underlying_bar_contract_validates() -> None:
    bar = UnderlyingBar(
        symbol="SYNTH",
        timestamp=datetime(2025, 1, 15),
        open=100.0,
        high=101.0,
        low=99.5,
        close=100.5,
        volume=1_000_000,
        adj_close=100.5,
    )
    assert bar.close == 100.5


def test_ensure_data_dirs(tmp_path: Path) -> None:
    data_dir = tmp_path / "test_data_dirs"
    ensure_data_dirs(data_dir)
    assert (data_dir / "raw").exists()
    assert (data_dir / "processed").exists()


def test_fixture_dataframe_shape() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "SYNTH",
                "expiration": date(2040, 2, 16),
                "strike": 100.0,
                "right": "call",
                "bid": 2.0,
                "ask": 2.2,
            }
        ]
    )
    assert {"symbol", "expiration", "strike", "right", "bid", "ask"}.issubset(frame.columns)
