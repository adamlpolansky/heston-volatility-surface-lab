# Public-data policy

This repository is provider-independent while data licensing permission is unresolved.

## Excluded from the public repository

- ThetaData or any other restricted-provider market data;
- raw or processed quote rows, cached responses and provider exports;
- private single-name empirical studies or conclusions;
- provider-derived IV surfaces, calibration parameters, metrics, plots or tables;
- credentials, API keys and local secret files; and
- claims of empirical profitability, mispricing or executable arbitrage.

The synthetic generator was selected independently for software validation. It does not
reconstruct, approximate or target any private study.

## Enforcement

The default dependency set contains no provider client. The public evidence command, tests and
CI require no credential and issue no provider request. A publication guard allowlists tracked
paths, rejects data/report formats and scans tracked text for secrets and prohibited private
identifiers. CI regenerates the aggregate JSON and SVG and requires a clean diff.

The optional provider adapter is code only. It defaults to dry-run behavior and is outside the
public evidence path. No permission to access, store or redistribute provider data is implied.
