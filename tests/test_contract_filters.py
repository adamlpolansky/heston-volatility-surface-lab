from __future__ import annotations

from datetime import date

import pandas as pd

from heston_arb_lab.data.contract_filters import ContractFilter, filter_contract_universe


def test_contract_filter_applies_dte_moneyness_and_limits() -> None:
    contracts = pd.DataFrame(
        [
            {"symbol": "SYNTH", "expiration": date(2040, 7, 10), "strike": 90, "right": "call"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 17), "strike": 100, "right": "call"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 17), "strike": 101, "right": "put"},
            {"symbol": "SYNTH", "expiration": date(2040, 10, 17), "strike": 100, "right": "put"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 17), "strike": 140, "right": "call"},
        ]
    )
    config = ContractFilter(
        dte_min=7,
        dte_max=45,
        moneyness_min=0.9,
        moneyness_max=1.1,
        rights=("call", "put"),
        max_expirations=2,
        max_strikes_per_expiry_right=1,
        max_contracts=2,
    )

    selected = filter_contract_universe(
        contracts, asof=date(2040, 7, 2), underlying_price=100.0, config=config
    )

    assert len(selected) == 2
    assert set(selected["right"]) == {"call", "put"}
    assert selected["dte"].between(7, 45).all()
    assert selected["moneyness"].between(0.9, 1.1).all()
