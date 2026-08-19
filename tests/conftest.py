from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from heston_arb_lab.surface.surface_builder import (
    SurfaceBuildConfig,
    build_surface,
    synthetic_option_chain,
)


@pytest.fixture()
def asof_date() -> date:
    return date(2025, 1, 15)


@pytest.fixture()
def synthetic_surface(asof_date: date) -> pd.DataFrame:
    quotes = synthetic_option_chain(asof=asof_date)
    return build_surface(quotes, SurfaceBuildConfig(spot=100.0, asof=asof_date, rate=0.04))
