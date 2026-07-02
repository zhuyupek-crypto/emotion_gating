# Cache Availability Audit

- Window: 2023-01-01 to 2023-03-31.
- Physical 2023 cache present in inspected roots: `False`.
- Field-level information is derivable from T-1 or earlier daily data, so the generator logic is PIT-safe if the batch is completed before 09:05 on T.
- File mtimes in the inspected cache roots are 2026 build times and cannot prove historical pre-open availability.
- Current Phase 1D worktree has no local `project_cache/features/auction_yiqian_prepare/2023.parquet`; inspected main workspace cache also lacks `2023.parquet`.