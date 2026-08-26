from __future__ import annotations

import os
import socket
from datetime import date
from typing import Any

import pandas as pd
import pytest

from heston_arb_lab.surface.surface_builder import (
    SurfaceBuildConfig,
    build_surface,
    synthetic_option_chain,
)


@pytest.fixture(autouse=True)
def block_network_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the CI offline contract executable rather than documentary."""

    if os.environ.get("HESTON_LAB_OFFLINE") != "1":
        return

    def denied(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("network access is forbidden in offline tests")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture()
def asof_date() -> date:
    return date(2025, 1, 15)


@pytest.fixture()
def synthetic_surface(asof_date: date) -> pd.DataFrame:
    quotes = synthetic_option_chain(asof=asof_date)
    return build_surface(quotes, SurfaceBuildConfig(spot=100.0, asof=asof_date, rate=0.04))
