# Changelog

## Unreleased

- Build configuration access errors from safe location parts and controlled native
  details. Preserve missing-file categories while removing unsafe native
  filenames, attributes, notes and exception chains.
- Fall back to a plain errno-bearing `OSError` when a native subclass constructor
  fails or returns something other than an `OSError` instance, preserving valid
  exception chaining and excluding the invalid result.
- Protect direct and cached source reads, including local dotenv reads before
  custom source hooks, without replacing content parsers or changing recipes.
- Reduce diagnostic payloads process-wide on `fsspec`, `fsspec.http`,
  `fsspec.caching` and `fsspec.asyn`; preserve records, severity and handlers,
  including background-cache diagnostics. Local paths and path segments remain
  visible, and file-content errors retain their existing diagnostics.
