"""Contract-universe filtering helpers for bounded real-data jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class ContractFilter:
    """DTE, moneyness, and hard-limit contract filter."""

    dte_min: int
    dte_max: int
    moneyness_min: float
    moneyness_max: float
    rights: tuple[str, ...]
    max_expirations: int
    max_strikes_per_expiry_right: int
    max_contracts: int


def normalize_contracts(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Return a normalized option-contract dataframe."""

    if frame.empty:
        return pd.DataFrame(columns=["symbol", "expiration", "strike", "right"])
    result = frame.copy()
    result.columns = [str(col).lower() for col in result.columns]
    rename = {"root": "symbol", "exp": "expiration", "expiry": "expiration"}
    result = result.rename(columns={old: new for old, new in rename.items() if old in result})
    if "symbol" not in result:
        result["symbol"] = symbol.upper()
    result["symbol"] = result["symbol"].astype(str).str.upper()
    result["expiration"] = pd.to_datetime(result["expiration"]).dt.date
    result["strike"] = pd.to_numeric(result["strike"], errors="coerce")
    result["right"] = result["right"].map(_normalize_right)
    return result.dropna(subset=["expiration", "strike", "right"])


def _normalize_right(value: object) -> str | None:
    text = str(value).strip().lower()
    if text in {"c", "call", "calls"}:
        return "call"
    if text in {"p", "put", "puts"}:
        return "put"
    return None


def filter_contract_universe(
    contracts: pd.DataFrame,
    *,
    asof: date,
    underlying_price: float,
    config: ContractFilter,
) -> pd.DataFrame:
    """Filter contracts by DTE, moneyness, rights, and configured hard limits."""

    if contracts.empty:
        return contracts.copy()
    frame = contracts.copy()
    frame["dte"] = frame["expiration"].map(lambda exp: (exp - asof).days)
    frame["moneyness"] = frame["strike"].astype(float) / float(underlying_price)
    frame = frame[
        frame["dte"].between(config.dte_min, config.dte_max)
        & frame["moneyness"].between(config.moneyness_min, config.moneyness_max)
        & frame["right"].isin(config.rights)
    ].copy()
    if frame.empty:
        return frame

    expirations = sorted(frame["expiration"].unique())[: config.max_expirations]
    frame = frame[frame["expiration"].isin(expirations)].copy()
    selected_groups: list[pd.DataFrame] = []
    for _, group in frame.groupby(["expiration", "right"], sort=True):
        ordered = group.assign(distance=(group["moneyness"] - 1.0).abs()).sort_values(
            ["distance", "strike"]
        )
        selected_groups.append(ordered.head(config.max_strikes_per_expiry_right))
    selected = pd.concat(selected_groups, ignore_index=True) if selected_groups else frame.head(0)
    selected = _balanced_contract_head(selected, config.rights, config.max_contracts)
    return selected.drop(columns=["distance"], errors="ignore").reset_index(drop=True)


def _balanced_contract_head(
    frame: pd.DataFrame, rights: tuple[str, ...], limit: int
) -> pd.DataFrame:
    """Limit contracts while preserving both calls and puts when possible."""

    if len(frame) <= limit:
        return frame.sort_values(["expiration", "right", "strike"])
    buckets = {
        right: group.sort_values(["expiration", "strike"]).reset_index(drop=True)
        for right, group in frame.groupby("right")
    }
    selected_rows: list[pd.Series] = []
    cursor = 0
    ordered_rights = [right for right in rights if right in buckets]
    while len(selected_rows) < limit and ordered_rights:
        made_progress = False
        for right in ordered_rights:
            bucket = buckets[right]
            if cursor < len(bucket):
                selected_rows.append(bucket.iloc[cursor])
                made_progress = True
                if len(selected_rows) >= limit:
                    break
        if not made_progress:
            break
        cursor += 1
    return pd.DataFrame(selected_rows).sort_values(["expiration", "right", "strike"])
