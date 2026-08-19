from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from heston_arb_lab.data.contract_filters import ContractFilter
from heston_arb_lab.data.thetadata_client import (
    ThetaDataAdapter,
    ThetaDataSchemaError,
    discover_contract_universe,
    ingest_option_quote_ticks,
    normalize_option_contracts_response,
    normalize_option_quotes_response,
    select_one_strike_per_symbol,
    select_tiny_surface_contracts,
    to_internal_right,
    to_thetadata_date,
    to_thetadata_right,
    to_thetadata_strike,
)


class RecordingThetaClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def option_list_contracts(
        self,
        request_type: str,
        date: date,
        symbol: str | list[str] | None = None,
        max_dte: int | None = None,
    ) -> list[dict[str, object]]:
        kwargs = {
            "request_type": request_type,
            "date": date,
            "symbol": symbol,
            "max_dte": max_dte,
        }
        self.calls.append(("option_list_contracts", kwargs))
        return [
            {
                "symbol": "SYNTH",
                "expiration": date.replace(day=17),
                "strike": 100.0,
                "right": "call",
            }
        ]

    def option_history_quote(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("option_history_quote", kwargs))
        return []


def test_list_contracts_maps_request_date_to_official_date_parameter() -> None:
    client = RecordingThetaClient()
    adapter = ThetaDataAdapter(client=client)

    adapter.list_contracts(
        request_type="quote",
        request_date=date(2040, 7, 2),
        symbol="SYNTH",
        max_dte=45,
    )

    _, kwargs = client.calls[-1]
    assert kwargs["request_type"] == "quote"
    assert kwargs["date"] == date(2040, 7, 2)
    assert kwargs["symbol"] == "SYNTH"
    assert kwargs["max_dte"] == 45


def test_adapter_defaults_to_pandas_dataframe_type_for_live_client() -> None:
    adapter = ThetaDataAdapter()

    assert adapter.dataframe_type == "pandas"


def test_invalid_contract_request_type_raises_before_client_call() -> None:
    client = RecordingThetaClient()
    adapter = ThetaDataAdapter(client=client)

    with pytest.raises(ValueError, match="request_type"):
        adapter.list_contracts(request_type="EOD", request_date=date(2040, 7, 2))

    assert client.calls == []


def test_quote_pipeline_discovers_contracts_with_quote_request_type() -> None:
    client = RecordingThetaClient()
    adapter = ThetaDataAdapter(client=client)
    config = ContractFilter(
        dte_min=7,
        dte_max=45,
        moneyness_min=0.9,
        moneyness_max=1.1,
        rights=("call", "put"),
        max_expirations=4,
        max_strikes_per_expiry_right=15,
        max_contracts=80,
    )

    discover_contract_universe(
        adapter,
        symbol="SYNTH",
        asof=date(2040, 7, 2),
        underlying_price=100.0,
        config=config,
    )

    _, kwargs = client.calls[-1]
    assert kwargs["request_type"] == "quote"


def test_historical_quotes_passes_official_quote_history_parameters() -> None:
    client = RecordingThetaClient()
    adapter = ThetaDataAdapter(client=client)

    adapter.historical_quotes(
        symbol="SYNTH",
        expiration=date(2040, 7, 17),
        strike="100.0",
        right="call",
        date=date(2040, 7, 2),
        start_time="09:30:00",
        end_time="16:00:00",
        interval="tick",
    )

    _, kwargs = client.calls[-1]
    assert kwargs == {
        "symbol": "SYNTH",
        "expiration": date(2040, 7, 17),
        "strike": "100.0",
        "right": "call",
        "date": date(2040, 7, 2),
        "start_time": "09:30:00",
        "end_time": "16:00:00",
        "interval": "tick",
    }


def test_right_mapping_supports_compact_and_official_values() -> None:
    assert to_internal_right("C") == "C"
    assert to_internal_right("call") == "C"
    assert to_thetadata_right("CALL") == "call"
    assert to_internal_right("P") == "P"
    assert to_internal_right("put") == "P"
    assert to_thetadata_right("PUT") == "put"
    assert to_thetadata_right("C") == "call"
    assert to_thetadata_right("P") == "put"


def test_strike_mapping_removes_filename_safe_encoding() -> None:
    assert to_thetadata_strike(407.5) == "407.5"
    assert to_thetadata_strike("407.5") == "407.5"
    assert to_thetadata_strike("407p5") == "407.5"
    assert to_thetadata_strike("465p0") == "465.0"


def test_thetadata_date_mapping_returns_python_date() -> None:
    assert to_thetadata_date(date(2040, 7, 2)) == date(2040, 7, 2)
    assert to_thetadata_date(pd.Timestamp("2040-07-02T13:30:00Z")) == date(2040, 7, 2)
    assert to_thetadata_date("2040-07-02") == date(2040, 7, 2)


def test_invalid_right_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unsupported option right"):
        to_thetadata_right("straddle")


def test_historical_quotes_maps_compact_right_to_thetadata_right() -> None:
    client = RecordingThetaClient()
    adapter = ThetaDataAdapter(client=client)

    adapter.historical_quotes(
        symbol="SYNTH",
        expiration=date(2040, 7, 17),
        strike="100.0",
        right="C",
        date=date(2040, 7, 2),
    )

    _, kwargs = client.calls[-1]
    assert kwargs["right"] == "call"


def test_historical_quotes_maps_filename_safe_strike_and_dates() -> None:
    client = RecordingThetaClient()
    adapter = ThetaDataAdapter(client=client)

    adapter.historical_quotes(
        symbol="SYNTH",
        expiration="2040-07-17",
        strike="407p5",
        right="CALL",
        date=pd.Timestamp("2040-07-02"),
    )

    _, kwargs = client.calls[-1]
    assert kwargs["expiration"] == date(2040, 7, 17)
    assert kwargs["strike"] == "407.5"
    assert kwargs["right"] == "call"
    assert kwargs["date"] == date(2040, 7, 2)


def test_one_strike_selector_picks_nearest_target_dte_and_atm_strike() -> None:
    contracts = pd.DataFrame(
        [
            {"symbol": "SYNTH", "expiration": date(2040, 7, 4), "strike": 100, "right": "call"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 4), "strike": 100, "right": "put"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 8), "strike": 400, "right": "call"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 8), "strike": 400, "right": "put"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 8), "strike": 407.5, "right": "C"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 8), "strike": 407.5, "right": "P"},
            {"symbol": "SYNTH", "expiration": date(2040, 7, 20), "strike": 407.5, "right": "call"},
        ]
    )

    selected = select_one_strike_per_symbol(
        contracts,
        symbol="SYNTH",
        quote_date=date(2040, 7, 1),
        underlying_reference_price=406.0,
        target_dte=7,
        min_dte=1,
        max_dte=14,
    )

    assert selected["expiration"].tolist() == [date(2040, 7, 8), date(2040, 7, 8)]
    assert selected["strike"].tolist() == [407.5, 407.5]
    assert selected["right"].tolist() == ["call", "put"]
    assert selected.attrs["warnings"] == []


def test_one_strike_selector_warns_when_one_side_is_missing() -> None:
    contracts = pd.DataFrame(
        [
            {"symbol": "SYNTH3", "expiration": date(2040, 7, 8), "strike": 200, "right": "call"},
            {"symbol": "SYNTH3", "expiration": date(2040, 7, 8), "strike": 205, "right": "put"},
        ]
    )

    selected = select_one_strike_per_symbol(
        contracts,
        symbol="SYNTH3",
        quote_date=date(2040, 7, 1),
        underlying_reference_price=200.0,
    )

    assert selected["right"].tolist() == ["call"]
    assert "missing rights put" in selected.attrs["warnings"][0]


def test_tiny_surface_selector_picks_two_expiries_and_five_atm_strikes() -> None:
    rows = []
    for expiration in (date(2040, 7, 4), date(2040, 7, 8), date(2040, 7, 15)):
        for strike in (390.0, 400.0, 405.0, 407.5, 410.0, 420.0):
            for right in ("CALL", "PUT"):
                rows.append(
                    {
                        "symbol": "SYNTH",
                        "expiration": expiration,
                        "strike": strike,
                        "right": right,
                    }
                )

    selected = select_tiny_surface_contracts(
        pd.DataFrame(rows),
        symbol="SYNTH",
        quote_date=date(2040, 7, 1),
        underlying_reference_price=406.0,
        target_dte=7,
        dte_min=1,
        dte_max=21,
        expiries_per_symbol_date=2,
        strikes_around_atm=5,
        rights=("call", "put"),
        max_contracts=20,
    )

    assert selected["expiration"].nunique() == 2
    assert selected["strike"].nunique() == 5
    assert len(selected) == 20
    assert set(selected["right"]) == {"call", "put"}
    assert selected["expiration"].tolist() == sorted(selected["expiration"].tolist())
    assert selected.attrs["warnings"] == []


def test_tiny_surface_selector_caps_contracts_and_warns() -> None:
    rows = [
        {"symbol": "SYNTH", "expiration": date(2040, 7, 8), "strike": strike, "right": right}
        for strike in (400.0, 405.0, 410.0)
        for right in ("call", "put")
    ]

    selected = select_tiny_surface_contracts(
        pd.DataFrame(rows),
        symbol="SYNTH",
        quote_date=date(2040, 7, 1),
        underlying_reference_price=406.0,
        target_dte=7,
        dte_min=1,
        dte_max=21,
        expiries_per_symbol_date=1,
        strikes_around_atm=3,
        rights=("call", "put"),
        max_contracts=4,
    )

    assert len(selected) == 4
    assert "capped" in selected.attrs["warnings"][0]


def test_ingest_quote_ticks_passes_probe_style_parameters_and_writes_non_empty_parquet(
    tmp_path,
) -> None:
    class NonEmptyQuoteClient(RecordingThetaClient):
        def option_history_quote(self, **kwargs: object) -> list[dict[str, object]]:
            self.calls.append(("option_history_quote", kwargs))
            return [
                {
                    "symbol": "SYNTH",
                    "expiration": date(2040, 7, 17),
                    "strike": 407.5,
                    "right": "call",
                    "timestamp": pd.Timestamp("2040-07-02T13:30:00Z"),
                    "bid_size": 10,
                    "bid_exchange": 4,
                    "bid": 1.2,
                    "bid_condition": 50,
                    "ask_size": 12,
                    "ask_exchange": 4,
                    "ask": 1.4,
                    "ask_condition": 50,
                }
            ]

    client = NonEmptyQuoteClient()
    adapter = ThetaDataAdapter(client=client)
    contracts = pd.DataFrame(
        [
            {
                "symbol": "SYNTH",
                "expiration": date(2040, 7, 17),
                "strike": 407.5,
                "right": "CALL",
            }
        ]
    )

    manifest = ingest_option_quote_ticks(
        adapter,
        contracts=contracts,
        symbol="SYNTH",
        quote_date=date(2040, 7, 2),
        output_root=tmp_path / "raw" / "thetadata" / "options_quotes",
        manifest_path=tmp_path / "cache" / "manifest.json",
        interval="5m",
        dry_run=False,
    )

    _, kwargs = client.calls[-1]
    assert kwargs["expiration"] == date(2040, 7, 17)
    assert kwargs["strike"] == "407.5"
    assert kwargs["right"] == "call"
    assert kwargs["date"] == date(2040, 7, 2)
    assert kwargs["interval"] == "5m"
    assert manifest["success_count"] == 1
    assert manifest["no_rows_count"] == 0
    files = list((tmp_path / "raw").glob("**/*.parquet"))
    assert len(files) == 1
    assert len(pd.read_parquet(files[0])) == 1


def test_ingest_quote_ticks_maps_filename_safe_strike_to_api_value(tmp_path) -> None:
    class NonEmptyQuoteClient(RecordingThetaClient):
        def option_history_quote(self, **kwargs: object) -> list[dict[str, object]]:
            self.calls.append(("option_history_quote", kwargs))
            return [
                {
                    "symbol": "SYNTH",
                    "expiration": date(2040, 7, 17),
                    "strike": "407.5",
                    "right": "call",
                    "timestamp": pd.Timestamp("2040-07-02T13:30:00Z"),
                    "bid_size": 10,
                    "bid_exchange": 4,
                    "bid": 1.2,
                    "bid_condition": 50,
                    "ask_size": 12,
                    "ask_exchange": 4,
                    "ask": 1.4,
                    "ask_condition": 50,
                }
            ]

    client = NonEmptyQuoteClient()
    adapter = ThetaDataAdapter(client=client)
    contracts = pd.DataFrame(
        [
            {
                "symbol": "SYNTH",
                "expiration": "2040-07-17",
                "strike": "407p5",
                "right": "C",
            }
        ]
    )

    ingest_option_quote_ticks(
        adapter,
        contracts=contracts,
        symbol="SYNTH",
        quote_date=date(2040, 7, 2),
        output_root=tmp_path / "raw" / "thetadata" / "options_quotes",
        manifest_path=tmp_path / "cache" / "manifest.json",
        dry_run=False,
    )

    _, kwargs = client.calls[-1]
    assert kwargs["strike"] == "407.5"
    assert kwargs["right"] == "call"


def test_empty_quote_response_is_not_success_and_does_not_write_parquet(tmp_path) -> None:
    client = RecordingThetaClient()
    adapter = ThetaDataAdapter(client=client)
    contracts = pd.DataFrame(
        [
            {
                "symbol": "SYNTH",
                "expiration": date(2040, 7, 17),
                "strike": 100.0,
                "right": "C",
            }
        ]
    )

    manifest = ingest_option_quote_ticks(
        adapter,
        contracts=contracts,
        symbol="SYNTH",
        quote_date=date(2040, 7, 2),
        output_root=tmp_path / "raw" / "thetadata" / "options_quotes",
        manifest_path=tmp_path / "cache" / "manifest.json",
        dry_run=False,
    )

    assert manifest["success_count"] == 0
    assert manifest["no_rows_count"] == 1
    assert manifest["contracts"][0]["status"] == "no_rows"
    assert not list((tmp_path / "raw").glob("**/*.parquet"))


def test_too_large_quote_response_is_not_written(tmp_path) -> None:
    class LargeQuoteClient(RecordingThetaClient):
        def option_history_quote(self, **kwargs: object) -> list[dict[str, object]]:
            self.calls.append(("option_history_quote", kwargs))
            return [
                {
                    "symbol": "SYNTH",
                    "expiration": date(2040, 7, 17),
                    "strike": 100.0,
                    "right": "call",
                    "timestamp": pd.Timestamp("2040-07-02T13:30:00Z") + pd.Timedelta(minutes=index),
                    "bid_size": 10,
                    "bid_exchange": 4,
                    "bid": 1.2,
                    "bid_condition": 50,
                    "ask_size": 12,
                    "ask_exchange": 4,
                    "ask": 1.4,
                    "ask_condition": 50,
                }
                for index in range(3)
            ]

    client = LargeQuoteClient()
    adapter = ThetaDataAdapter(client=client)
    contracts = pd.DataFrame(
        [
            {
                "symbol": "SYNTH",
                "expiration": date(2040, 7, 17),
                "strike": 100.0,
                "right": "C",
            }
        ]
    )

    manifest = ingest_option_quote_ticks(
        adapter,
        contracts=contracts,
        symbol="SYNTH",
        quote_date=date(2040, 7, 2),
        output_root=tmp_path / "raw" / "thetadata" / "options_quotes",
        manifest_path=tmp_path / "cache" / "manifest.json",
        interval="5m",
        dry_run=False,
        max_rows=2,
    )

    assert manifest["success_count"] == 0
    assert manifest["too_large_count"] == 1
    assert manifest["contracts"][0]["status"] == "too_large"
    assert not list((tmp_path / "raw").glob("**/*.parquet"))


def test_quote_download_exception_does_not_write_empty_parquet(tmp_path) -> None:
    class FailingQuoteClient(RecordingThetaClient):
        def option_history_quote(self, **kwargs: object) -> list[dict[str, object]]:
            self.calls.append(("option_history_quote", kwargs))
            raise RuntimeError("ThetaData temporary failure")

    client = FailingQuoteClient()
    adapter = ThetaDataAdapter(client=client)
    contracts = pd.DataFrame(
        [
            {
                "symbol": "SYNTH",
                "expiration": date(2040, 7, 17),
                "strike": 100.0,
                "right": "C",
            }
        ]
    )

    manifest = ingest_option_quote_ticks(
        adapter,
        contracts=contracts,
        symbol="SYNTH",
        quote_date=date(2040, 7, 2),
        output_root=tmp_path / "raw" / "thetadata" / "options_quotes",
        manifest_path=tmp_path / "cache" / "manifest.json",
        dry_run=False,
        retry_attempts=1,
        sleep_seconds=0,
    )

    assert manifest["success_count"] == 0
    assert manifest["failure_count"] == 1
    assert manifest["contracts"][0]["status"] == "failed"
    assert not list((tmp_path / "raw").glob("**/*.parquet"))


def test_normalize_option_quotes_response_preserves_successful_thetadata_schema() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "SYNTH",
                "expiration": date(2040, 7, 2),
                "strike": "465.0",
                "right": "call",
                "timestamp": pd.Timestamp("2040-07-01T13:30:00Z"),
                "bid_size": 10,
                "bid_exchange": 4,
                "bid": 1.2,
                "bid_condition": 50,
                "ask_size": 12,
                "ask_exchange": 4,
                "ask": 1.4,
                "ask_condition": 50,
            }
        ]
    )

    normalized = normalize_option_quotes_response(frame)

    assert len(normalized) == 1
    assert list(normalized.columns) == [
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
    assert normalized.iloc[0]["strike"] == 465.0
    assert normalized.iloc[0]["right"] == "call"


def test_normalize_option_contracts_response_accepts_docs_pandas_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "synth",
                "expiration": date(2040, 7, 17),
                "strike": 100,
                "right": "C",
            }
        ]
    )

    normalized = normalize_option_contracts_response(frame)

    assert normalized.to_dict("records") == [
        {
            "symbol": "SYNTH",
            "expiration": date(2040, 7, 17),
            "strike": 100,
            "right": "call",
        }
    ]


def test_normalize_option_contracts_response_accepts_alias_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "underlying_symbol": "synth2",
                "expiration_date": "2040-07-17",
                "strike_price": "200.5",
                "call_put": "put",
            }
        ]
    )

    normalized = normalize_option_contracts_response(frame)

    assert normalized.iloc[0]["symbol"] == "SYNTH2"
    assert normalized.iloc[0]["expiration"] == date(2040, 7, 17)
    assert normalized.iloc[0]["strike"] == 200.5
    assert normalized.iloc[0]["right"] == "put"


def test_normalize_option_contracts_response_accepts_polars_if_available() -> None:
    pl = pytest.importorskip("polars")
    frame = pl.DataFrame(
        {
            "root": ["SYNTH3"],
            "expiry": ["2040-07-17"],
            "strike": [150.0],
            "cp": ["P"],
        }
    )

    normalized = normalize_option_contracts_response(frame)

    assert normalized.iloc[0]["symbol"] == "SYNTH3"
    assert normalized.iloc[0]["right"] == "put"


def test_normalize_option_contracts_response_missing_columns_raises_schema_error() -> None:
    frame = pd.DataFrame([{"symbol": "SYNTH", "strike": 100.0}])

    with pytest.raises(ThetaDataSchemaError, match="missing required columns"):
        normalize_option_contracts_response(frame)
