# Provider integration

ThetaData support is an optional adapter for users who independently possess authorized
credentials and data rights. The adapter wraps documented Python-library method names behind a
narrow boundary and defaults to `dry_run=True`.

Live access requires all of the following:

1. install the `providers` extra;
2. place `THETADATA_API_KEY` only in the process environment or an external secret manager;
3. instantiate `ThetaDataAdapter(dry_run=False)` explicitly;
4. choose an output location under a Git-ignored local directory;
5. confirm that the intended access, storage, and use comply with provider terms.

The adapter never logs a credential. CI does not set provider credentials, perform live
requests, or download market data. Provider-derived files are outside the public contract and
must not be committed or redistributed.
