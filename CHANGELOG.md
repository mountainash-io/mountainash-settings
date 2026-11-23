# Changelog

## Unreleased

- Build configuration access errors from safe location parts and controlled native
  details. Preserve missing-file categories while removing unsafe native
  filenames, attributes, notes and exception chains.
- Protect direct and cached source reads, including local dotenv reads before
  custom source hooks, without replacing content parsers or changing recipes.
- Reduce diagnostic payloads process-wide on `fsspec`, `fsspec.http`,
  `fsspec.caching` and `fsspec.asyn`; preserve records, severity and handlers,
  including background-cache diagnostics. Local paths and path segments remain
  visible, and file-content errors retain their existing diagnostics.
