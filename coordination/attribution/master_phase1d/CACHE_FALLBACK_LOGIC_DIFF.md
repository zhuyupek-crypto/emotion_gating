# Cache Fallback Logic Diff

- Runtime accessor returns `None` when the yearly physical feature file is absent.
- When rows are present, runtime sorts by `rank` and attempts to recompute `left_ok` through `_auction_yiqian_batch_left_pressure_api`.
- Phase 1C `SOURCE_LIMITED_PREPARED_RECORD` rows label the prepared source as `PROJECT_AUCTION_PREPARE_CACHE`; Phase 1D found no inspected 2023 physical cache file, so those rows should be treated as prepared-source observations with unknown physical cache provenance.
- No formal strategy, engine, compat, or data-reader behavior was changed in Phase 1D.