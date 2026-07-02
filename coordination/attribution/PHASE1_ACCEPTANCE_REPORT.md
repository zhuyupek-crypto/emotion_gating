# Phase 1 Acceptance Report

## Phase 1 Goal

Phase 1 establishes an observation contract for the motherboard strategy without optimizing parameters, computing Alpha/EV, or running counterfactual branches. The goal is to prove that Observer v1.0 can record the actual 2023 signal -> gate -> resource -> order -> trade lineage without changing strategy behavior.

## Frozen Baselines

- Runtime environment: `CODE_NATIVE_COMPUTED_ENVIRONMENT`
- Observer contract version: `1.0`
- Downstream schema: `0.3`
- Upstream scan/source schema: `0.4`
- Formal strategy SHA: `621a9c968473d73dfa1699be0a16714790e4f93ab950957c0a3f88f4f34bcc8e`
- Instrumented strategy SHA: `30761614fafffb2a1b88ebe88f0c1ab85e2d65cb8f006f92917a5da35b2e24be`

## Q1 Canonical Correction

The archived Phase 1C Q1 909-signal ledger is `SUPERSEDED_FOR_ATTRIBUTION`. Phase 1D/1E canonically replaces it with the reproducible computed-environment Q1 baseline:

- Q1 signal count: `531`
- Q1 signal key SHA: `60cb1a92bcf14da9b9409a635ef3e29ba552de3133bdc588218c2126d979ebf5`
- Q1 terminal state SHA: `a24157da4db8a0c03afeff1d3021355ad9a38aeb5c3ff64f8ffed1bc8e4b9a9f`
- Q1 source mode SHA: `5e5d3d5f86856e82890f8e4238652b1177928b8a14cee14454a8ac6791ecca54`
- Q1 behavior parity: `True`

## 2023 Full-Year Behavior Parity

- Final value: `1258307.590000002`
- Orders: `259`
- Trades: `259`
- B0/I0/I1 trades, orders, equity, state, and handler profile equal: `True`

## Full-Year Event Closure

- SIGNAL_EVENT rows: `2524`
- Closed signals: `2524`
- UNRESOLVED: `0`
- Duplicate signal keys: `0`
- Unmapped trades: `0`
- Trade lineage mapping rate: `1.0`

## Branch Signal Counts

| Branch | Signal Count |
| --- | ---: |
| Auction | 1442 |
| Scorpion | 632 |
| ZB | 279 |
| YJJ | 125 |
| RZQ | 46 |
| **Total** | **2524** |

## Evidence Levels By Branch

All five branches have complete prepared-candidate parent mapping for SIGNAL_EVENT. However, Phase 1 does not claim exhaustive pre-prepared raw rejection coverage. See `master_phase1e/EVIDENCE_SCOPE_MATRIX.csv` for the executable table.

- Auction: `PREPARED_PARENT_ONLY`; actual source mode canonicalized to `AUCTION_PREPARE_COMPUTED`, but the full computed pre-cap mask/rank rejection funnel is not exhaustively emitted.
- Scorpion/YJJ/ZB/RZQ: `PREPARED_PARENT_ONLY`; raw parent/source identity is present for candidates reached by the actual runtime path, while rejected pre-prepared raw universes are not exhaustive.

## Fully Observed Facts

- Prepared candidates in `SIGNAL_EVENT`
- Terminal states and terminal reason codes
- Actual motherboard routing/resource/order/trade lineage
- Order intents and mapped trade outcomes under `MASTER_ACTUAL`
- Scan-run invocation/source-mode status for the formal runtime path
- Year-end open-position lineage summary

## Prepared Parent Only Facts

- RAW_PATTERN_EVENT should be used as prepared/source parent evidence unless a branch is explicitly marked `EXHAUSTIVE_RAW_PATTERN` in the evidence matrix.
- Phase 1 cannot infer missing rejected raw candidates for `PREPARED_PARENT_ONLY` branches.

## Questions Phase 1 Cannot Answer

- Full pre-prepared scan filter EV for `PREPARED_PARENT_ONLY` branches
- Bare-branch counterfactual performance
- Alpha/EV optimization
- Independent emotion-panel attribution
- 2018-2025 matrix stability

## Phase 2 Inputs

Allowed: canonical 2023 Observer v1.0 facts and the submitted manifests/hashes. Forbidden: the old 909 ledger, unmanifested local facts, unknown caches, optimization outputs, and future counterfactual facts mixed into `MASTER_ACTUAL`.

## Final Conclusion

`PASS_AND_FREEZE`

`Phase 1 = CLOSED`

`Phase 2 = READY`
