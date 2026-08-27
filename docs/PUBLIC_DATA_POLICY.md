# Public-data policy

The reproducible software-validation path is provider-independent and entirely synthetic. A
separate, isolated directory contains only the frozen aggregate Heston/SSVI artifacts covered by
specific written publication permission for the TSLA options study from 30 June through 2 July
2026.

## Excluded from the public repository

- any provider-derived artifact outside the exact approved aggregate allowlist;
- raw or processed quote rows, cached responses and provider exports;
- individual contracts, individual option-contract identifiers or contract-level symbols, actual
  strikes, NBBO, bid/ask values or sizes;
- per-strike IV or fitted values, ranked candidates and detailed case studies;
- API payloads, Parquet files, databases and downloadable market datasets;
- credentials, API keys and local secret files; and
- claims of empirical profitability, mispricing or executable arbitrage.

The synthetic generator was selected independently for software validation. It does not
reconstruct, approximate or target any private study.

## Enforcement

The default dependency set contains no provider client. The synthetic evidence command, tests and
CI require no credential and issue no provider request. A fail-closed, defense-in-depth publication
guard verifies the exact paths and SHA-256 hashes of all files in the approved directory, rejects
additional files there, checks attribution and disclaimer wording, rejects prohibited data/report
formats elsewhere, and scans tracked text and `HEAD` history for secrets and private identifiers.
The guard does not replace human review of the diff against the approved Theta Data package and
does not provide an absolute legal guarantee. CI regenerates the synthetic JSON and SVG and
requires a clean diff.

The optional provider adapter is code only. It defaults to dry-run behavior and remains outside
the public evidence path. The narrow permission covering the approved aggregates grants no
provider access and no right for third parties to sublicense or redistribute those artifacts.
