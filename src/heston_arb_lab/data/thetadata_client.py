"""ThetaData Python-library adapter with safe credential handling."""

from __future__ import annotations

import datetime as dt
import json
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

from heston_arb_lab.config import load_thetadata_api_key, resolve_thetadata_credentials
from heston_arb_lab.data.contract_filters import (
    ContractFilter,
    filter_contract_universe,
)
from heston_arb_lab.data.storage import write_parquet_partitioned

VALID_CONTRACT_REQUEST_TYPES = {"quote", "trade"}
CONTRACT_COLUMNS = ["symbol", "expiration", "strike", "right"]
QUOTE_COLUMNS = [
    "symbol",
    "expiration",
    "strike",
    "right",
    "timestamp",
    "bid_size",
    "bid_exchange",
    "bid",
    "bid_condition",
    "ask_size",
    "ask_exchange",
    "ask",
    "ask_condition",
]
CONTRACT_COLUMN_ALIASES = {
    "symbol": ("symbol", "root", "underlying", "underlying_symbol"),
    "expiration": ("expiration", "expiry", "exp", "expiration_date"),
    "strike": ("strike", "strike_price"),
    "right": ("right", "option_right", "option_type", "cp", "call_put"),
}
QUOTE_COLUMN_ALIASES = {
    **CONTRACT_COLUMN_ALIASES,
    "timestamp": ("timestamp", "time", "datetime", "ms_of_day"),
    "bid_size": ("bid_size", "bidsize"),
    "bid_exchange": ("bid_exchange", "bid_exch", "bid_exchange_id"),
    "bid": ("bid", "bid_price"),
    "bid_condition": ("bid_condition", "bid_cond"),
    "ask_size": ("ask_size", "asksize"),
    "ask_exchange": ("ask_exchange", "ask_exch", "ask_exchange_id"),
    "ask": ("ask", "ask_price"),
    "ask_condition": ("ask_condition", "ask_cond"),
}

logger = logging.getLogger(__name__)


class ThetaDataUnavailableError(RuntimeError):
    """Raised when real ThetaData access cannot be initialized."""


class ThetaDataSchemaError(RuntimeError):
    """Raised when a ThetaData response cannot be normalized safely."""


@dataclass(frozen=True)
class ThetaDataAuthReport:
    """Secret-free ThetaData auth status."""

    credentials_present: bool
    source: str


def _drop_none(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def describe_response(raw: Any) -> dict[str, Any]:
    """Return secret-free response diagnostics for logs and probe commands."""

    diagnostics: dict[str, Any] = {"response_type": type(raw).__name__}
    columns = getattr(raw, "columns", None)
    if columns is not None:
        diagnostics["columns"] = [str(column) for column in columns]
    shape = getattr(raw, "shape", None)
    if shape is not None:
        diagnostics["shape"] = tuple(shape)
    elif hasattr(raw, "__len__"):
        with suppress(TypeError):
            diagnostics["row_count"] = len(raw)
    dtypes = getattr(raw, "dtypes", None)
    if dtypes is not None:
        if isinstance(dtypes, pd.Series):
            diagnostics["dtypes"] = {str(key): str(value) for key, value in dtypes.items()}
        else:
            diagnostics["dtypes"] = [str(dtype) for dtype in dtypes]
    return diagnostics


def normalize_option_contracts_response(raw: Any) -> pd.DataFrame:
    """Normalize ThetaData option contract responses to canonical columns."""

    frame = _response_to_pandas(raw)
    diagnostics = describe_response(raw)
    diagnostics["pandas_columns"] = [str(column) for column in frame.columns]
    diagnostics["pandas_shape"] = tuple(frame.shape)
    logger.debug("ThetaData contract response diagnostics: %s", diagnostics)

    rename = _build_column_rename(
        frame,
        aliases=CONTRACT_COLUMN_ALIASES,
        required=CONTRACT_COLUMNS,
        endpoint="option_list_contracts",
        raw=raw,
        diagnostics=diagnostics,
    )

    result = frame.rename(columns=rename).loc[:, CONTRACT_COLUMNS].copy()
    result["symbol"] = result["symbol"].astype(str).str.upper()
    result["expiration"] = pd.to_datetime(result["expiration"], errors="coerce").dt.date
    result["strike"] = pd.to_numeric(result["strike"], errors="coerce")
    result["right"] = result["right"].map(to_thetadata_right)
    return result.dropna(subset=CONTRACT_COLUMNS).reset_index(drop=True)


def normalize_option_quotes_response(raw: Any) -> pd.DataFrame:
    """Normalize ThetaData option quote history responses to canonical columns."""

    frame = _response_to_pandas(raw)
    diagnostics = describe_response(raw)
    diagnostics["pandas_columns"] = [str(column) for column in frame.columns]
    diagnostics["pandas_shape"] = tuple(frame.shape)
    logger.debug("ThetaData quote response diagnostics: %s", diagnostics)
    if frame.empty:
        return pd.DataFrame(columns=QUOTE_COLUMNS)

    rename = _build_column_rename(
        frame,
        aliases=QUOTE_COLUMN_ALIASES,
        required=QUOTE_COLUMNS,
        endpoint="option_history_quote",
        raw=raw,
        diagnostics=diagnostics,
    )
    result = frame.rename(columns=rename).loc[:, QUOTE_COLUMNS].copy()
    result["symbol"] = result["symbol"].astype(str).str.upper()
    result["expiration"] = pd.to_datetime(result["expiration"], errors="coerce").dt.date
    result["strike"] = pd.to_numeric(result["strike"], errors="coerce")
    result["right"] = result["right"].map(to_thetadata_right)
    numeric_columns = (
        "bid_size",
        "bid_exchange",
        "bid",
        "bid_condition",
        "ask_size",
        "ask_exchange",
        "ask",
        "ask_condition",
    )
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["symbol", "expiration", "strike", "right"]).reset_index(drop=True)


def _build_column_rename(
    frame: pd.DataFrame,
    *,
    aliases: dict[str, tuple[str, ...]],
    required: list[str],
    endpoint: str,
    raw: Any,
    diagnostics: dict[str, Any],
) -> dict[Any, str]:
    original_columns = [str(column) for column in frame.columns]
    normalized_lookup = {_normalize_column_name(column): column for column in frame.columns}
    rename: dict[Any, str] = {}
    missing: list[str] = []
    for canonical in required:
        source = next(
            (
                normalized_lookup[_normalize_column_name(alias)]
                for alias in aliases[canonical]
                if _normalize_column_name(alias) in normalized_lookup
            ),
            None,
        )
        if source is None:
            missing.append(canonical)
        else:
            rename[source] = canonical
    if missing:
        raise ThetaDataSchemaError(
            f"ThetaData {endpoint} response missing required columns "
            f"{missing}; response_type={type(raw).__name__}; "
            f"shape={diagnostics.get('shape', diagnostics.get('pandas_shape'))}; "
            f"columns={original_columns}"
        )
    return rename


def _response_to_pandas(raw: Any) -> pd.DataFrame:
    if isinstance(raw, pd.DataFrame):
        return raw.copy()
    if hasattr(raw, "to_pandas"):
        converted = raw.to_pandas()
        if isinstance(converted, pd.DataFrame):
            return converted.copy()
    if isinstance(raw, dict):
        for key in ("data", "rows", "contracts", "response"):
            value = raw.get(key)
            if isinstance(value, (list, tuple)):
                return pd.DataFrame(value)
        return pd.DataFrame(raw)
    return pd.DataFrame(raw)


def _normalize_column_name(column: object) -> str:
    return str(column).strip().lower().replace(" ", "_").replace("-", "_")


def to_internal_right(value: object) -> str:
    """Normalize an option right to internal compact `C`/`P` form."""

    text = str(value).strip().lower()
    if text in {"c", "call", "calls"}:
        return "C"
    if text in {"p", "put", "puts"}:
        return "P"
    raise ValueError(f"Unsupported option right {value!r}; expected C/P/call/put")


def to_thetadata_right(value: object) -> str:
    """Normalize an option right to official ThetaData `call`/`put` form."""

    internal = to_internal_right(value)
    return "call" if internal == "C" else "put"


def to_thetadata_strike(value: object) -> str:
    """Normalize a strike for ThetaData API calls without filename-safe encodings."""

    text = str(value).strip()
    if not text:
        raise ValueError("ThetaData strike cannot be empty")
    if "p" in text.lower() and "." not in text:
        text = text.lower().replace("p", ".")
    strike = float(text)
    return str(strike)


def to_thetadata_date(value: object) -> dt.date:
    """Normalize dates for ThetaData calls to Python ``datetime.date`` objects."""

    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Unsupported ThetaData date value {value!r}")
    return cast(dt.date, pd.Timestamp(parsed).date())


class FakeThetaDataClient:
    """Small deterministic fake used for tests, demos, and dry runs."""

    def option_list_expirations(self, symbol: str | list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "symbol": [symbol if isinstance(symbol, str) else symbol[0]],
                "expiration": [dt.date(2025, 1, 17)],
            }
        )

    def option_list_strikes(self, symbol: str | list[str], expiration: dt.date) -> pd.DataFrame:
        del expiration
        rows = [
            {"symbol": symbol if isinstance(symbol, str) else symbol[0], "strike": strike}
            for strike in (95.0, 100.0, 105.0)
        ]
        return pd.DataFrame(rows)

    def option_list_contracts(
        self,
        request_type: str,
        date: dt.date,
        symbol: str | list[str] | None = None,
        max_dte: int | None = None,
    ) -> pd.DataFrame:
        del request_type, date, max_dte
        underlying = symbol if isinstance(symbol, str) else "SYNTH"
        rows = []
        for strike in (95.0, 100.0, 105.0):
            for right in ("call", "put"):
                rows.append(
                    {
                        "symbol": underlying,
                        "expiration": dt.date(2025, 1, 17),
                        "strike": strike,
                        "right": right,
                    }
                )
        return pd.DataFrame(rows)

    def option_snapshot_quote(
        self,
        symbol: str,
        expiration: dt.date | str,
        strike: str = "*",
        right: str = "both",
        **_: Any,
    ) -> pd.DataFrame:
        del expiration, strike, right
        now = dt.datetime(2025, 1, 15, 15, 30)
        rows = []
        for option_right in ("call", "put"):
            for option_strike in (95.0, 100.0, 105.0):
                mid = max(0.4, 5.0 - abs(option_strike - 100.0) * 0.25)
                rows.append(
                    {
                        "timestamp": now,
                        "symbol": symbol,
                        "expiration": dt.date(2025, 1, 17),
                        "strike": option_strike,
                        "right": option_right,
                        "bid_size": 10,
                        "bid_exchange": 0,
                        "bid": round(mid - 0.05, 4),
                        "bid_condition": 0,
                        "ask_size": 10,
                        "ask_exchange": 0,
                        "ask": round(mid + 0.05, 4),
                        "ask_condition": 0,
                    }
                )
        return pd.DataFrame(rows)

    def option_snapshot_greeks_all(
        self, symbol: str, expiration: dt.date | str, **kwargs: Any
    ) -> pd.DataFrame:
        quotes = self.option_snapshot_quote(symbol=symbol, expiration=expiration, **kwargs)
        quotes["iv"] = 0.2
        quotes["delta"] = 0.5
        quotes["gamma"] = 0.02
        quotes["vega"] = 0.1
        quotes["theta"] = -0.02
        quotes["rho"] = 0.01
        return quotes

    def option_history_greeks_all(
        self,
        symbol: str,
        expiration: dt.date,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        del start_date, end_date
        return self.option_snapshot_greeks_all(symbol=symbol, expiration=expiration, **kwargs)

    def option_history_quote(
        self,
        symbol: str,
        expiration: dt.date | str,
        interval: str = "tick",
        date: dt.date | None = None,
        strike: str = "*",
        right: str = "both",
        start_time: str = "09:30:00",
        end_time: str = "16:00:00",
        **_: Any,
    ) -> pd.DataFrame:
        del interval, date, start_time, end_time
        return self.option_snapshot_quote(
            symbol=symbol, expiration=expiration, strike=strike, right=right
        )


class ThetaDataAdapter:
    """Thin wrapper around official `thetadata.ThetaClient` methods."""

    def __init__(
        self,
        *,
        explicit_api_key: str | None = None,
        repo_root: Path | None = None,
        mdds_type: str = "PROD",
        dataframe_type: str = "pandas",
        credentials_file: Path | None = None,
        dry_run: bool = True,
        client: Any | None = None,
    ) -> None:
        self.explicit_api_key = explicit_api_key
        self.repo_root = repo_root or Path.cwd()
        self.mdds_type = mdds_type
        self.dataframe_type = dataframe_type
        self.credentials_file = credentials_file
        self.dry_run = dry_run
        self._client = client

    def auth_report(self) -> ThetaDataAuthReport:
        """Return a secret-free credential status report."""

        status, _ = resolve_thetadata_credentials(self.explicit_api_key, self.repo_root)
        if status.present:
            return ThetaDataAuthReport(True, status.source)
        if self.credentials_file is not None:
            return ThetaDataAuthReport(True, "explicit credentials file")
        return ThetaDataAuthReport(False, "missing")

    def connect(self) -> Any:
        """Create or return the underlying ThetaData client."""

        if self._client is not None:
            return self._client
        if self.dry_run:
            self._client = FakeThetaDataClient()
            return self._client

        api_key = load_thetadata_api_key(self.explicit_api_key, self.repo_root)
        try:
            from thetadata import ThetaClient
        except ImportError as exc:
            raise ThetaDataUnavailableError(
                "The `thetadata` package is not installed. Install with `pip install thetadata`."
            ) from exc

        kwargs: dict[str, Any] = {
            "dataframe_type": self.dataframe_type,
            "mdds_type": self.mdds_type,
        }
        if api_key:
            kwargs["api_key"] = api_key
        elif self.credentials_file is not None:
            kwargs["creds_file"] = str(self.credentials_file)
        else:
            raise ThetaDataUnavailableError(
                "ThetaData credentials are missing. Set THETADATA_API_KEY in the process "
                "environment, or keep the adapter in dry-run mode."
            )

        self._client = ThetaClient(**kwargs)
        return self._client

    def list_expirations(self, symbol: str | list[str]) -> Any:
        """Call `option_list_expirations(symbol=...)`."""

        return self.connect().option_list_expirations(symbol=symbol)

    def list_strikes(self, symbol: str | list[str], expiration: dt.date) -> Any:
        """Call `option_list_strikes(symbol=..., expiration=...)`."""

        return self.connect().option_list_strikes(symbol=symbol, expiration=expiration)

    def list_contracts(
        self,
        request_type: str,
        request_date: dt.date | None = None,
        date: dt.date | None = None,
        symbol: str | list[str] | None = None,
        max_dte: int | None = None,
    ) -> Any:
        """Call `option_list_contracts(...)` with official parameter names."""

        normalized_request_type = request_type.lower()
        if normalized_request_type not in VALID_CONTRACT_REQUEST_TYPES:
            raise ValueError(
                "ThetaData option_list_contracts request_type must be one of "
                f"{sorted(VALID_CONTRACT_REQUEST_TYPES)}, got {request_type!r}"
            )
        request_date_value = date or request_date
        if request_date_value is None:
            raise ValueError("ThetaData option_list_contracts requires `date` or `request_date`")
        return self.connect().option_list_contracts(
            **_drop_none(
                {
                    "request_type": normalized_request_type,
                    "date": request_date_value,
                    "symbol": symbol,
                    "max_dte": max_dte,
                }
            )
        )

    def snapshot_quotes(
        self,
        symbol: str,
        expiration: dt.date | str,
        strike: str = "*",
        right: str = "both",
        max_dte: int | None = None,
        strike_range: int | None = None,
        min_time: str | None = None,
    ) -> Any:
        """Call `option_snapshot_quote(...)`."""

        return self.connect().option_snapshot_quote(
            **_drop_none(
                {
                    "symbol": symbol,
                    "expiration": expiration,
                    "strike": strike,
                    "right": right,
                    "max_dte": max_dte,
                    "strike_range": strike_range,
                    "min_time": min_time,
                }
            )
        )

    def snapshot_all_greeks(
        self,
        symbol: str,
        expiration: dt.date | str,
        strike: str = "*",
        right: str = "both",
        annual_dividend: float | None = None,
        rate_type: str | None = None,
        rate_value: float | None = None,
        stock_price: float | None = None,
        version: str = "latest",
        max_dte: int | None = None,
        strike_range: int | None = None,
        min_time: str | None = None,
        use_market_value: bool | None = None,
    ) -> Any:
        """Call `option_snapshot_greeks_all(...)`."""

        return self.connect().option_snapshot_greeks_all(
            **_drop_none(
                {
                    "symbol": symbol,
                    "expiration": expiration,
                    "strike": strike,
                    "right": right,
                    "annual_dividend": annual_dividend,
                    "rate_type": rate_type,
                    "rate_value": rate_value,
                    "stock_price": stock_price,
                    "version": version,
                    "max_dte": max_dte,
                    "strike_range": strike_range,
                    "min_time": min_time,
                    "use_market_value": use_market_value,
                }
            )
        )

    def historical_all_greeks(
        self,
        symbol: str,
        expiration: dt.date,
        interval: str = "1m",
        request_date: dt.date | None = None,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        strike: str = "*",
        right: str = "both",
        start_time: str = "09:30:00",
        end_time: str = "16:00:00",
    ) -> Any:
        """Call `option_history_greeks_all(...)` for historical IV/Greeks."""

        return self.connect().option_history_greeks_all(
            **_drop_none(
                {
                    "date": request_date,
                    "symbol": symbol,
                    "expiration": expiration,
                    "strike": strike,
                    "right": right,
                    "start_time": start_time,
                    "end_time": end_time,
                    "interval": interval,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
        )

    def historical_quotes(
        self,
        *,
        symbol: str,
        expiration: dt.date | str,
        strike: object = "*",
        right: str = "both",
        date: dt.date | None = None,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        start_time: str = "09:30:00",
        end_time: str = "16:00:00",
        interval: str = "tick",
        max_dte: int | None = None,
        strike_range: int | None = None,
    ) -> Any:
        """Call official `option_history_quote(...)` with validated parameter names."""

        api_right = "both" if str(right).strip().lower() == "both" else to_thetadata_right(right)
        api_strike = "*" if str(strike).strip() == "*" else to_thetadata_strike(strike)
        return self.connect().option_history_quote(
            **_drop_none(
                {
                    "symbol": symbol,
                    "expiration": to_thetadata_date(expiration),
                    "strike": api_strike,
                    "right": api_right,
                    "date": to_thetadata_date(date) if date is not None else None,
                    "start_time": start_time,
                    "end_time": end_time,
                    "interval": interval,
                    "max_dte": max_dte,
                    "strike_range": strike_range,
                    "start_date": (
                        to_thetadata_date(start_date) if start_date is not None else None
                    ),
                    "end_date": to_thetadata_date(end_date) if end_date is not None else None,
                }
            )
        )

    def historical_trades(self, **kwargs: Any) -> Any:
        """Call `option_history_trade(...)` when the installed client exposes it."""

        client = self.connect()
        if not hasattr(client, "option_history_trade"):
            raise ThetaDataUnavailableError(
                "Installed ThetaData client has no option_history_trade"
            )
        return client.option_history_trade(**_drop_none(kwargs))


def _safe_filename(contract: pd.Series) -> str:
    right = to_internal_right(contract["right"])
    strike = to_thetadata_strike(contract["strike"]).replace(".", "p")
    return f"expiry={contract['expiration']}_right={right}_strike={strike}.parquet"


def discover_contract_universe(
    adapter: ThetaDataAdapter,
    *,
    symbol: str,
    asof: dt.date,
    underlying_price: float,
    config: ContractFilter,
    cache_dir: Path | None = None,
    request_type: str = "quote",
) -> pd.DataFrame:
    """Discover and filter option contracts for a symbol/date."""

    raw = adapter.list_contracts(
        request_type=request_type,
        request_date=asof,
        symbol=symbol,
        max_dte=config.dte_max,
    )
    contracts = normalize_option_contracts_response(raw)
    selected = filter_contract_universe(
        contracts,
        asof=asof,
        underlying_price=underlying_price,
        config=config,
    )
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        selected.to_json(cache_dir / f"{symbol}_{asof}_contracts.json", orient="records", indent=2)
    return selected


def select_one_strike_per_symbol(
    contracts: Any,
    *,
    symbol: str,
    quote_date: dt.date,
    underlying_reference_price: float,
    target_dte: int = 7,
    min_dte: int = 1,
    max_dte: int = 14,
    include_rights: tuple[str, ...] = ("call", "put"),
) -> pd.DataFrame:
    """Select one near-ATM strike at the expiry closest to the target DTE."""

    warnings: list[str] = []
    requested_rights = tuple(to_thetadata_right(right) for right in include_rights)
    frame = normalize_option_contracts_response(contracts)
    if frame.empty:
        selected = pd.DataFrame(columns=[*CONTRACT_COLUMNS, "dte", "moneyness"])
        selected.attrs["warnings"] = [f"{symbol}: no contracts returned by ThetaData"]
        return selected

    quote_date_api = to_thetadata_date(quote_date)
    frame = frame[frame["symbol"].eq(symbol.upper())].copy()
    frame["dte"] = frame["expiration"].map(lambda expiration: (expiration - quote_date_api).days)
    frame["moneyness"] = frame["strike"].astype(float) / float(underlying_reference_price)
    frame = frame[
        frame["dte"].between(min_dte, max_dte) & frame["right"].isin(requested_rights)
    ].copy()
    if frame.empty:
        selected = pd.DataFrame(columns=[*CONTRACT_COLUMNS, "dte", "moneyness"])
        selected.attrs["warnings"] = [f"{symbol}: no contracts in DTE range {min_dte}-{max_dte}"]
        return selected

    expiry_rank = (
        frame[["expiration", "dte"]]
        .drop_duplicates()
        .assign(dte_distance=lambda data: (data["dte"] - target_dte).abs())
        .sort_values(["dte_distance", "dte", "expiration"])
    )
    expiry = expiry_rank.iloc[0]["expiration"]
    expiry_frame = frame[frame["expiration"].eq(expiry)].copy()
    strike_rank = (
        expiry_frame[["strike"]]
        .drop_duplicates()
        .assign(atm_distance=lambda data: (data["strike"] - underlying_reference_price).abs())
        .sort_values(["atm_distance", "strike"])
    )
    strike = float(strike_rank.iloc[0]["strike"])
    selected = expiry_frame[expiry_frame["strike"].astype(float).eq(strike)].copy()
    selected = selected[selected["right"].isin(requested_rights)].copy()
    right_order = {right: index for index, right in enumerate(requested_rights)}
    selected["right_order"] = selected["right"].map(right_order)
    selected = selected.sort_values(["right_order", "expiration", "strike"]).drop(
        columns=["right_order"]
    )
    missing_rights = [right for right in requested_rights if right not in set(selected["right"])]
    if missing_rights:
        warnings.append(
            f"{symbol}: selected {expiry} {strike:g} missing rights {', '.join(missing_rights)}"
        )
    selected = selected.reset_index(drop=True)
    selected.attrs["warnings"] = warnings
    return selected


def select_tiny_surface_contracts(
    contracts: Any,
    *,
    symbol: str,
    quote_date: dt.date,
    underlying_reference_price: float,
    target_dte: int,
    dte_min: int,
    dte_max: int,
    expiries_per_symbol_date: int,
    strikes_around_atm: int,
    rights: tuple[str, ...],
    max_contracts: int | None = None,
) -> pd.DataFrame:
    """Select a deterministic tiny ATM surface across expiries, strikes, and rights."""

    warnings: list[str] = []
    requested_rights = tuple(to_thetadata_right(right) for right in rights)
    frame = normalize_option_contracts_response(contracts)
    empty_columns = [*CONTRACT_COLUMNS, "dte", "moneyness"]
    if frame.empty:
        selected = pd.DataFrame(columns=empty_columns)
        selected.attrs["warnings"] = [f"{symbol}: no contracts returned by ThetaData"]
        return selected

    quote_date_api = to_thetadata_date(quote_date)
    frame = frame[frame["symbol"].eq(symbol.upper())].copy()
    frame["dte"] = frame["expiration"].map(lambda expiration: (expiration - quote_date_api).days)
    frame["moneyness"] = frame["strike"].astype(float) / float(underlying_reference_price)
    frame = frame[
        frame["dte"].between(dte_min, dte_max) & frame["right"].isin(requested_rights)
    ].copy()
    if frame.empty:
        selected = pd.DataFrame(columns=empty_columns)
        selected.attrs["warnings"] = [f"{symbol}: no contracts in DTE range {dte_min}-{dte_max}"]
        return selected

    expiry_rank = (
        frame[["expiration", "dte"]]
        .drop_duplicates()
        .assign(dte_distance=lambda data: (data["dte"] - target_dte).abs())
        .sort_values(["dte_distance", "dte", "expiration"])
        .head(expiries_per_symbol_date)
    )
    selected_groups: list[pd.DataFrame] = []
    for expiry in expiry_rank["expiration"]:
        expiry_frame = frame[frame["expiration"].eq(expiry)].copy()
        strikes = (
            expiry_frame[["strike"]]
            .drop_duplicates()
            .assign(atm_distance=lambda data: (data["strike"] - underlying_reference_price).abs())
            .sort_values(["atm_distance", "strike"])
            .head(strikes_around_atm)["strike"]
            .astype(float)
            .tolist()
        )
        expiry_selected = expiry_frame[expiry_frame["strike"].astype(float).isin(strikes)].copy()
        for strike in strikes:
            available = set(
                expiry_selected[expiry_selected["strike"].astype(float).eq(float(strike))]["right"]
            )
            missing_rights = [right for right in requested_rights if right not in available]
            if missing_rights:
                warnings.append(
                    f"{symbol}: selected {expiry} {strike:g} missing rights "
                    f"{', '.join(missing_rights)}"
                )
        selected_groups.append(expiry_selected)

    selected = (
        pd.concat(selected_groups, ignore_index=True)
        if selected_groups
        else pd.DataFrame(columns=empty_columns)
    )
    right_order = {right: index for index, right in enumerate(requested_rights)}
    selected["right_order"] = selected["right"].map(right_order)
    selected = selected.sort_values(["symbol", "expiration", "strike", "right_order"]).drop(
        columns=["right_order"]
    )
    if max_contracts is not None and len(selected) > max_contracts:
        warnings.append(
            f"{symbol}: selected {len(selected)} contracts capped to max_contracts {max_contracts}"
        )
        selected = selected.head(max_contracts).copy()
    selected = selected.reset_index(drop=True)
    selected.attrs["warnings"] = warnings
    return selected


def ingest_option_quote_ticks(
    adapter: ThetaDataAdapter,
    *,
    contracts: pd.DataFrame,
    symbol: str,
    quote_date: dt.date,
    output_root: Path,
    manifest_path: Path,
    start_time: str = "09:30:00",
    end_time: str = "16:00:00",
    interval: str = "tick",
    dry_run: bool = True,
    overwrite: bool = False,
    max_rows: int = 250_000,
    sleep_seconds: float = 0.25,
    retry_attempts: int = 3,
) -> dict[str, Any]:
    """Download or plan bounded option quote ticks and write a manifest."""

    manifest: dict[str, Any] = {
        "symbol": symbol,
        "quote_date": str(quote_date),
        "dry_run": dry_run,
        "contracts": [],
        "success_count": 0,
        "no_rows_count": 0,
        "too_large_count": 0,
        "failure_count": 0,
        "row_count": 0,
        "warnings": [],
    }
    partition = output_root / f"symbol={symbol}" / f"date={quote_date}"
    for contract_index, (_, contract) in enumerate(contracts.iterrows()):
        expiration = to_thetadata_date(contract["expiration"])
        strike_api = to_thetadata_strike(contract["strike"])
        strike = float(strike_api)
        quote_date_api = to_thetadata_date(quote_date)
        internal_right = to_internal_right(contract["right"])
        api_right = to_thetadata_right(contract["right"])
        target = partition / _safe_filename(contract)
        record: dict[str, Any] = {
            "symbol": symbol,
            "quote_date": str(quote_date),
            "expiration": str(expiration),
            "strike": strike,
            "strike_api": strike_api,
            "right": internal_right,
            "thetadata_right": api_right,
            "interval": interval,
            "path": str(target),
            "status": "planned" if dry_run else "pending",
            "rows": 0,
            "api_params": {
                "symbol": symbol,
                "expiration": str(expiration),
                "strike": strike_api,
                "right": api_right,
                "date": str(quote_date_api),
                "start_time": start_time,
                "end_time": end_time,
                "interval": interval,
            },
        }
        request_diagnostics = {
            "symbol": symbol,
            "expiration": str(expiration),
            "strike_api": strike_api,
            "right_api": api_right,
            "date": str(quote_date_api),
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
        }
        if contract_index < 3:
            logger.info("ThetaData quote request params: %s", request_diagnostics)
        if dry_run:
            manifest["contracts"].append(record)
            continue
        if target.exists() and not overwrite:
            existing_rows = _existing_parquet_rows(target)
            record["rows"] = existing_rows
            if existing_rows > 0:
                record["status"] = "skipped_existing"
                manifest["success_count"] += 1
                manifest["row_count"] += existing_rows
            else:
                record["status"] = "skipped_existing_empty"
                manifest["no_rows_count"] += 1
            manifest["contracts"].append(record)
            continue
        try:

            def fetch_quote_history(
                expiration: dt.date = expiration,
                strike_api: str = strike_api,
                api_right: str = api_right,
                quote_date_api: dt.date = quote_date_api,
            ) -> Any:
                return adapter.historical_quotes(
                    symbol=symbol,
                    expiration=expiration,
                    strike=strike_api,
                    right=api_right,
                    date=quote_date_api,
                    start_time=start_time,
                    end_time=end_time,
                    interval=interval,
                )

            frame = _retry(
                fetch_quote_history,
                attempts=retry_attempts,
                sleep_seconds=sleep_seconds,
            )
            if contract_index < 3:
                returned = describe_response(frame)
                logger.info(
                    "ThetaData quote response diagnostics: %s",
                    {**request_diagnostics, "returned_shape": returned.get("shape")},
                )
            df = normalize_option_quotes_response(frame)
            if df.empty:
                record["status"] = "no_rows"
                manifest["no_rows_count"] += 1
                manifest["contracts"].append(record)
                time.sleep(sleep_seconds)
                continue
            if interval.lower() == "5m" and len(df) > 1_000:
                warning = (
                    "Expected interval data but received tick-like row count; "
                    "verify ThetaData interval parameter."
                )
                record["warning"] = warning
                manifest["warnings"].append(
                    {
                        "symbol": symbol,
                        "quote_date": str(quote_date_api),
                        "expiration": str(expiration),
                        "strike": strike_api,
                        "right": api_right,
                        "rows": len(df),
                        "warning": warning,
                    }
                )
                logger.warning("%s %s", warning, request_diagnostics)
            if len(df) > max_rows:
                warning = (
                    f"quote response rows {len(df)} exceed max_rows_per_contract {max_rows}; "
                    "skipping contract instead of truncating"
                )
                record["status"] = "too_large"
                record["rows"] = len(df)
                record["warning"] = warning
                manifest["too_large_count"] += 1
                manifest["warnings"].append(
                    {
                        "symbol": symbol,
                        "quote_date": str(quote_date_api),
                        "expiration": str(expiration),
                        "strike": strike_api,
                        "right": api_right,
                        "rows": len(df),
                        "warning": warning,
                    }
                )
                manifest["contracts"].append(record)
                time.sleep(sleep_seconds)
                continue
            df = _normalize_quote_ticks(df, symbol=symbol, contract=contract, quote_date=quote_date)
            written = write_parquet_partitioned(df, target)
            record["status"] = "success"
            record["rows"] = len(df)
            record["path"] = str(written[0])
            manifest["success_count"] += 1
            manifest["row_count"] += len(df)
        except Exception as exc:
            record["status"] = "failed"
            record["error_type"] = type(exc).__name__
            record["error"] = sanitize_thetadata_error(exc)
            manifest["failure_count"] += 1
        manifest["contracts"].append(record)
        time.sleep(sleep_seconds)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _existing_parquet_rows(path: Path) -> int:
    try:
        return len(pd.read_parquet(path))
    except Exception:
        return 0


def _retry(call: Any, *, attempts: int, sleep_seconds: float) -> Any:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < attempts:
                time.sleep(sleep_seconds * (2**attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry exhausted without an exception")


def sanitize_thetadata_error(exc: Exception) -> str:
    """Return a bounded, credential-safe exception message for manifests."""

    text = str(exc)
    for token in ("THETADATA_API_KEY", "api_key"):
        text = text.replace(token, "<credential-source>")
    return text[:500]


def _normalize_quote_ticks(
    frame: pd.DataFrame,
    *,
    symbol: str,
    contract: pd.Series,
    quote_date: dt.date,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "quote_date",
                "timestamp",
                "expiration",
                "strike",
                "right",
                "bid",
                "ask",
                "bid_size",
                "ask_size",
                "exchange",
                "condition",
            ]
        )
    df = frame.copy()
    df.columns = [str(col).lower() for col in df.columns]
    rename = {"ms_of_day": "timestamp", "bid_size": "bid_size", "ask_size": "ask_size"}
    df = df.rename(columns={old: new for old, new in rename.items() if old in df})
    if "timestamp" not in df:
        if "time" in df:
            df["timestamp"] = df["time"]
        else:
            df["timestamp"] = pd.Timestamp(quote_date)
    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        base = pd.Timestamp(quote_date, tz="America/New_York")
        df["timestamp"] = base + pd.to_timedelta(df["timestamp"].astype(float), unit="ms")
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if getattr(df["timestamp"].dt, "tz", None) is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(
            "America/New_York", nonexistent="shift_forward"
        )
    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    df["symbol"] = symbol.upper()
    df["quote_date"] = quote_date
    df["expiration"] = to_thetadata_date(contract["expiration"])
    df["strike"] = float(contract["strike"])
    df["right"] = to_thetadata_right(contract["right"])
    for col in ("bid", "ask", "bid_size", "ask_size"):
        if col not in df:
            df[col] = 0
    for col in ("exchange", "condition"):
        if col not in df:
            df[col] = None
    return df[
        [
            "symbol",
            "quote_date",
            "timestamp",
            "expiration",
            "strike",
            "right",
            "bid",
            "ask",
            "bid_size",
            "ask_size",
            "exchange",
            "condition",
        ]
    ]
