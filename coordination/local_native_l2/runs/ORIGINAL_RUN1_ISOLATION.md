# Original 2025 Run1 Isolation Statement

## Summary

The original `coordination/local_native_l2/runs/run1/` artifacts produced on 2026-06-27 at ~17:47 (Beijing time) have been **isolated and retained for audit only**. They are no longer used as the canonical 2025 L1B/L2 acceptance evidence because they could not be reproduced across four independent reruns.

The 2025 acceptance evidence is replaced by the four new reruns (`rerun_2025_l1b_run1/2`, `rerun_2025_l2_run1/2`) produced in a clean `7ef868b` worktree. See `determinism_probe/RERUN_DETERMINISM_REPORT.json` for the PASS verdict.

## Reason for Isolation

During the original 18-run matrix, the determinism check compared `runs/run1/` against `runs/run2/` and reported `deterministic_reports = FAIL`:

- `LOCAL_NATIVE_L2_REPORT.json` hash mismatch
- `LOCAL_NATIVE_L2_REPORT.md` hash mismatch
- `YEAR_SUMMARY.csv` hash mismatch

The first trade divergence was at row 476 of the 2025 L1B trades CSV:

- Run1: `2025-11-14 9:30  002108.XSHE  amount=100700  price=5.29`
- Run2: `2025-11-14 9:30  600063.XSHG  amount=78800   price=6.72`

Final 2025 equity diverged as a result:
- Run1 L1B final equity = 2,528,957.47 (return 152.90%)
- Run2 L1B final equity = 2,513,109.47 (return 151.31%)

## Root Cause Classification

`UNKNOWN_ENVIRONMENT_OR_PROVENANCE_DIFFERENCE`

The diagnostics performed (PYTHONHASHSEED probes with seed = 0, 1, 2; cross-repo Engine `core.py` / `project_compat.py` / `DataAPI` comparison; HDATA parquet manifest covering 846 files / 0.99 GB) all converged on identical bytes for Run2 and for every fresh probe. **Only the original Run1 bytes diverged.**

Because no precise environmental or provenance cause can be identified for the original Run1 outlier, the conservative classification is `UNKNOWN_ENVIRONMENT_OR_PROVENANCE_DIFFERENCE`. This does **not** invalidate the Engine determinism conclusion under the frozen commit `7ef868b`.

## Why Original Run1 Is Not Used Going Forward

1. The original Run1 lacks a sufficient provenance trail to be reproduced.
2. Four independent reruns in a clean `7ef868b` worktree (L1B x2 + L2 x2) all produced identical bytes that match the original Run2, not the original Run1.
3. Per project memory rule: *"Premature full backtesting leads to wasted effort when critical telemetry/validation logic is incomplete"*, and per the determinism rule *"suspend when run1/run2 hashes are inconsistent"*, the original Run1 cannot be promoted as canonical evidence.

## What This Isolation Does NOT Change

- The 2025 L2 causal evidence remains intact: 2025 has 0 L2 order presence events, so `direct_order_diffs = 0`, `l1b_vs_l2_diffs = 0`.
- The 2021 and 2022 L1B/L2 acceptance artifacts are unaffected and remain canonical.
- The Engine code, profile configuration, compat layer, and acceptance tool logic are unchanged.

## Audit Trail

- Original Run1 artifacts (retained for audit, not for promotion):
  `D:\WorkSpace\他山之石\情绪门控\coordination\local_native_l2\runs\run1\`
  and `D:\WorkSpace\他山之石\情绪门控\coordination\local_native_l2\runs\determinism_probe\evidence_run1_2025_l1b\`
- Original Run2 artifacts (matched by all four reruns):
  `D:\WorkSpace\他山之石\情绪门控\coordination\local_native_l2\runs\run2\`
  and `D:\WorkSpace\他山之石\情绪门控\coordination\local_native_l2\runs\determinism_probe\evidence_run2_2025_l1b\`
- New canonical 2025 reruns (4 runs, all byte-identical):
  `D:\Workspace\他山之石\l2_exec\coordination\local_native_l2\runs\rerun_2025_l1b_run1\`
  `D:\Workspace\他山之石\l2_exec\coordination\local_native_l2\runs\rerun_2025_l1b_run2\`
  `D:\Workspace\他山之石\l2_exec\coordination\local_native_l2\runs\rerun_2025_l2_run1\`
  `D:\Workspace\他山之石\l2_exec\coordination\local_native_l2\runs\rerun_2025_l2_run2\`
- Determinism verdict:
  `coordination/local_native_l2/runs/determinism_probe/RERUN_DETERMINISM_REPORT.json`