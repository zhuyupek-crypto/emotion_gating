# Phase 1D Auction Cache Provenance/PIT Audit

- Window: `2023-01-01` to `2023-03-31`.
- Conclusion: `PARTIAL`.
- Provider: runtime namespace delegates to `DataAPI.get_project_auction_yiqian_prepare`, then to `EmotionGateJQCompat.get_project_auction_yiqian_prepare`.
- Generator: `rebuild_from_archive.project_preprocess.build_auction_yiqian_prepare`.
- Physical 2023 cache found: `False`.
- Date-level rows compared: `51`.
- Mismatch rows: `25`.
- Replay alignment: `490/501` Phase 1C source-limited rows intersect the independent generator replay; residual differences are `23` membership rows and `2` field rows.

## Key Findings

1. `auction_yiqian_prepare` is a prepared-candidate cache, not raw auction pattern evidence.
2. The generator source is present and uses only T-1 or earlier daily data for candidate construction.
3. The inspected physical cache roots do not contain `auction_yiqian_prepare/2023.parquet`, so 2023Q1 Phase 1C `SOURCE_LIMITED_PREPARED_RECORD` rows cannot be certified as physical-cache-derived.
4. Phase 1D does not rewrite Phase 1C facts; it records the provenance gap as audit evidence for the next implementation boundary.

## Required Artifacts

- `PROVIDER_RESOLUTION.json`
- `AUCTION_CACHE_INVENTORY.json`
- `CACHE_SCHEMA_AUDIT.csv`
- `GENERATOR_MANIFEST.json`
- `GENERATOR_LOGIC.md`
- `AUCTION_CACHE_PIT_AUDIT.csv`
- `CACHE_AVAILABILITY_AUDIT.md`
- `CACHE_CANDIDATE_ALIGNMENT.csv`
- `CACHE_FIELD_ALIGNMENT.csv`
- `CACHE_RANK_CAP_AUDIT.csv`
- `LEFT_PRESSURE_ALIGNMENT.csv`
- `CACHE_FALLBACK_LOGIC_DIFF.md`
- `DATE_LEVEL_SUMMARY.csv`
- `MISMATCH_ROWS.csv`
- `UNKNOWN_PROVENANCE_ITEMS.csv`
- `RUN_MANIFEST.json`

## Unknown Provenance Items

- No physical auction_yiqian_prepare/2023.parquet found in inspected project cache roots.