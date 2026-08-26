from __future__ import annotations

import pytest

from heston_arb_lab.backtest.costs import CostConfig
from heston_arb_lab.backtest.engine import backtest_static_signals, round_trip_option_pnl
from heston_arb_lab.backtest.execution import option_exit_price, option_fill_price
from heston_arb_lab.backtest.metrics import compute_metrics
from heston_arb_lab.signals.ranking import score_signal


def test_bid_ask_execution_rules() -> None:
    assert option_fill_price("buy", 1.0, 1.2) == 1.2
    assert option_fill_price("sell", 1.0, 1.2) == 1.0
    assert option_exit_price("buy", 1.3, 1.5) == 1.3
    assert option_exit_price("sell", 1.3, 1.5) == 1.5


@pytest.mark.parametrize("side", ["", "hold", "BUY ", None])
def test_execution_fails_closed_for_unknown_or_missing_side(side: object) -> None:
    with pytest.raises(ValueError, match="side"):
        option_fill_price(side, 1.0, 1.2)  # type: ignore[arg-type]


def test_scoring_fails_closed_even_when_cost_is_precomputed() -> None:
    with pytest.raises(ValueError, match="side"):
        score_signal(
            {
                "gross_edge": 10.0,
                "estimated_cost": 1.0,
                "legs": [{"side": "unknown", "bid": 1.0, "ask": 1.1}],
            }
        )


def test_round_trip_long_and_short_accounting() -> None:
    cfg = CostConfig(option_fee_per_contract=0.0, slippage_bps=0.0)
    long_result = round_trip_option_pnl(
        side="buy",
        quantity=1.0,
        entry_bid=1.0,
        entry_ask=1.1,
        exit_bid=1.3,
        exit_ask=1.4,
        cost_config=cfg,
    )
    short_result = round_trip_option_pnl(
        side="sell",
        quantity=1.0,
        entry_bid=1.0,
        entry_ask=1.1,
        exit_bid=0.7,
        exit_ask=0.8,
        cost_config=cfg,
    )
    assert long_result["net_pnl"] == pytest.approx(20.0)
    assert short_result["net_pnl"] == pytest.approx(20.0)


def test_static_backtest_metrics() -> None:
    signals = [
        {
            "signal_id": "s1",
            "symbol": "SYNTH",
            "legs": [{"side": "buy", "bid": 1.0, "ask": 1.1, "mid": 1.05, "quantity": 1}],
        }
    ]
    trades = backtest_static_signals(signals, cost_config=CostConfig(slippage_bps=0.0))
    metrics = compute_metrics(trades)
    assert len(trades) == 1
    assert "net_pnl" in metrics
