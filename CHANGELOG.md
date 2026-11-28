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
  `fsspec.caching`, `fsspec.asyn` and `fsspec.reference`; preserve records, severity
  and handlers, including background-cache and reference-document diagnostics.
  Local paths and path segments remain
  visible, and file-content errors retain their existing diagnostics.
- Preserve local dotenv UPath storage options during the preliminary read before
  direct-construction source hooks, while retaining the ordinary source interface.
- Reject unsupported `FileTypeRegistry.register_type()` parser targets before
  changing registration; accept `yml` as a YAML target alongside custom extension
  aliases for the existing env, YAML, TOML and JSON parsers.
