# Optional provider boundary

The public project neither requires nor exercises a market-data provider. ThetaData support is
retained only as an optional code interface and defaults to `dry_run=True`. It contains no
credential, response cache or embedded provider output.

While licensing permission is unresolved, the public demo and CI must not instantiate a live
client, perform a provider request or publish any provider-derived artifact. The default
installation therefore excludes the provider extra.

Possession of this source code grants no provider access or data rights. Any future activation
would require separate written authorization, a licensing review and a publication-boundary
review. See the [public-data policy](PUBLIC_DATA_POLICY.md).
