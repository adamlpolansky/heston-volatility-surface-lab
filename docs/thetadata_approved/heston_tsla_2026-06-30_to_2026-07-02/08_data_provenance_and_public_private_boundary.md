# Data provenance and public/private boundary

## Provider and research scope

Options market data provided by Theta Data (https://www.thetadata.net).

This project is independent research by the author and is not reviewed, endorsed or sponsored by Theta Data.

The approved aggregate evidence covers TSLA equity options from 30 June through 2 July 2026.
The local research used historical US equity-options NBBO quotes reported by OPRA through Theta
Data, with yfinance bars used only as an approximate underlying reference. No provider or
underlying-reference request is part of the public repository, demo, tests or CI.

## Approved aggregate outputs

The public evidence is limited to the two frozen diagnostic figures and five frozen aggregate
tables listed in this directory's evidence index. These contain date-level observation and
calibration counts, aggregate fit-error and residual-to-spread metrics, aggregate parameter
summaries, research-gate outcomes, and aggregate audit counts. They are research diagnostics,
not trading conclusions or claims of profitability, mispricing or executable arbitrage.

The normalized Heston surface is constructed from the five published aggregate median
regularized-Heston parameters using normalized `F=100`, log-moneyness and a stable 2–12 DTE
grid. It does not contain the observed option grid, actual strikes, contracts, quotes or
per-strike implied volatility.

## Permanent public/private boundary

The repository does not contain raw or processed quote rows, individual option contracts,
symbols or actual strikes from the observation grid, NBBO observations, bid/ask values or sizes,
API payloads, response caches, Parquet files, databases, per-strike market/model IV or fitted
values, ranked candidates, detailed case studies, trade-level conclusions, secrets, credentials,
private reports, or a downloadable market dataset. Nothing published here permits reconstruction
of the underlying market observations.

Reproducing any real-data pathway requires the reader's own authorization and is outside the
public evidence, demo and CI. The synthetic evidence path remains independent and offline.

## Licence carve-out and retention

The repository's MIT License applies to the author's source code and materials explicitly
labelled synthetic. The approved Theta Data-derived aggregate artifacts are not offered under
the MIT License. Their publication relies on personal, non-commercial and non-transferable
written permission granted to Adam Luboš Polanský for this specific study. No right is granted
to third parties to sublicense or redistribute those provider-derived artifacts. The approved
aggregates may remain public after the subscription ends, while the permanent exclusions above
continue to apply.
