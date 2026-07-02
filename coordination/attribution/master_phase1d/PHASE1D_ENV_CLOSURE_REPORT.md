# Phase 1D Environment Closure Report

结论：`COMPUTED_ENVIRONMENT_CANONICALIZED`

Phase 1C archived signal count: `909`
Phase 1D closure signal count: `531`
Difference: `378`

## Branch Differences

- Auction: Phase1C `501`, Phase1D `270`, delta `-231`
- RZQ: Phase1C `61`, Phase1D `20`, delta `-41`
- Scorpion: Phase1C `30`, Phase1D `30`, delta `0`
- YJJ: Phase1C `89`, Phase1D `45`, delta `-44`
- ZB: Phase1C `228`, Phase1D `166`, delta `-62`

## Difference Types

- Auction / PHASE1C_ONLY: `231`
- RZQ / PHASE1C_ONLY: `41`
- YJJ / PHASE1C_ONLY: `44`
- ZB / PHASE1C_ONLY: `62`

## Cache Findings

- Phase 1C auction_yiqian_prepare/2023.parquet present now: `False`
- Phase 1D auction_yiqian_prepare/2023.parquet present now: `False`
- Historical existence during the original Phase 1C run: `HISTORICAL_EXISTENCE_UNKNOWN`.

## Baseline Decision

The 909-event environment is archived but not reproducibly frozen in the current worktrees. The 531-event computed-fallback environment is the current candidate canonical baseline, confirmed by two identical signal-key and terminal-state runs.

Canonical Q1 signal count: `531`
Canonical signal key SHA256: `60cb1a92bcf14da9b9409a635ef3e29ba552de3133bdc588218c2126d979ebf5`
Allow Phase 1E: `True` for the canonical computed baseline.

Repeatability: `True`
Source mode SHA256: `5e5d3d5f86856e82890f8e4238652b1177928b8a14cee14454a8ac6791ecca54`
