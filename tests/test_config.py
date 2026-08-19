from __future__ import annotations

from heston_arb_lab.config import resolve_thetadata_credentials


def test_credentials_are_environment_only(monkeypatch: object) -> None:
    monkeypatch.delenv("THETADATA_API_KEY", raising=False)  # type: ignore[attr-defined]
    status, secret = resolve_thetadata_credentials()

    assert status.present is False
    assert status.source == "missing"
    assert secret is None


def test_environment_credential_is_never_returned_in_status(monkeypatch: object) -> None:
    sentinel = "runtime-value-for-test-only"
    monkeypatch.setenv("THETADATA_API_KEY", sentinel)  # type: ignore[attr-defined]
    status, secret = resolve_thetadata_credentials()

    assert status.present is True
    assert status.source == "THETADATA_API_KEY environment"
    assert secret == sentinel
    assert sentinel not in repr(status)
