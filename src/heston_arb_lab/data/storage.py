"""Idempotent local storage helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

DATA_SUBDIRS = ("raw", "interim", "processed", "external")


def ensure_data_dirs(data_dir: Path) -> None:
    """Create the standard data directory layout."""

    for subdir in DATA_SUBDIRS:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)


def _to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame.copy()
    if hasattr(frame, "to_pandas"):
        converted = frame.to_pandas()
        if isinstance(converted, pd.DataFrame):
            return converted
    return pd.DataFrame(frame)


def write_parquet_partitioned(
    frame: Any,
    root: Path,
    partition_cols: list[str] | None = None,
    filename: str = "part.parquet",
) -> list[Path]:
    """Write a dataframe to parquet, optionally grouped by partition columns."""

    df = _to_pandas(frame)
    if not partition_cols:
        target = root if root.suffix == ".parquet" else root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(target, index=False)
        return [target]

    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for keys, group in df.groupby(partition_cols, dropna=False):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        partition = root
        for col, value in zip(partition_cols, key_tuple, strict=True):
            partition = partition / f"{col}={value}"
        partition.mkdir(parents=True, exist_ok=True)
        target = partition / filename
        group.to_parquet(target, index=False)
        written.append(target)
    return written


def read_parquet_dataset(root: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Read a parquet file or directory dataset."""

    return pd.read_parquet(root, columns=columns)


def duckdb_query(sql: str, database: Path | str = ":memory:") -> pd.DataFrame:
    """Execute a DuckDB SQL query and return a pandas dataframe."""

    import duckdb

    with duckdb.connect(str(database)) as connection:
        return connection.execute(sql).fetch_df()
