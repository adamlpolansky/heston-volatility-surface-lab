"""Environment-only configuration for optional provider integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CredentialStatus:
    """Secret-free description of credential discovery."""

    present: bool
    source: str


@dataclass(frozen=True)
class Settings:
    """Runtime settings that never load credentials from repository files."""

    data_dir: Path
    log_level: str
    thetadata_mdds_type: str


def load_settings(base_dir: Path | None = None) -> Settings:
    """Load non-secret settings from environment variables."""

    root = (base_dir or Path.cwd()).resolve()
    configured = Path(os.environ.get("HESTON_LAB_DATA_DIR", "work/provider-data"))
    data_dir = configured if configured.is_absolute() else root / configured
    return Settings(
        data_dir=data_dir,
        log_level=os.environ.get("HESTON_LAB_LOG_LEVEL", "INFO"),
        thetadata_mdds_type=os.environ.get("THETADATA_MDDS_TYPE", "PROD"),
    )


def clean_secret_value(raw_value: str | None) -> str | None:
    """Normalize a secret value without logging or persisting it."""

    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def resolve_thetadata_credentials(
    explicit_api_key: str | None = None,
    repo_root: Path | None = None,
) -> tuple[CredentialStatus, str | None]:
    """Resolve a ThetaData key from an explicit value or the process environment only."""

    del repo_root
    explicit = clean_secret_value(explicit_api_key)
    if explicit:
        return CredentialStatus(True, "explicit runtime value"), explicit
    environment = clean_secret_value(os.environ.get("THETADATA_API_KEY"))
    if environment:
        return CredentialStatus(True, "THETADATA_API_KEY environment"), environment
    return CredentialStatus(False, "missing"), None


def load_thetadata_api_key(
    explicit_api_key: str | None = None,
    repo_root: Path | None = None,
) -> str | None:
    """Return a runtime ThetaData key without reading repository-local files."""

    status, secret = resolve_thetadata_credentials(explicit_api_key, repo_root)
    return secret if status.present else None
