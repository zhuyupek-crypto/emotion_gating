# Phase 2 Input Contract

Phase 2 default analysis unit is `PREPARED_CANDIDATE` from canonical 2023 `SIGNAL_EVENT` under Observer Contract v1.0.

## Allowed Inputs By Table

| Input | Allowed Phase 2 Use | Required Companion Evidence |
| --- | --- | --- |
| Canonical 2023 SIGNAL_EVENT | prepared-candidate attribution and terminal funnel | RUN_MANIFEST, code SHA, stable signal/terminal hashes, evidence scope |
| DECISION_EVENT | actual downstream decision sequencing | signal_id linkage and schema 0.3 |
| TRADE_OUTCOME | MASTER_ACTUAL realized trade outcomes | order/trade lineage hash and outcome scope |
| ORDER_INTENT | order creation/resource lineage | order lineage hash |
| EXIT_INTENT | sell-side extension when present | manifest and explicit outcome scope |
| HANDLER_RESOURCE_SNAPSHOT | cash/slot/position context | handler coverage summary |
| SCAN_RUN_EVENT | scanner invocation/source status | scan_run hash and evidence scope |
| RAW_PATTERN_EVENT | parent/source evidence according to branch scope | EVIDENCE_SCOPE_MATRIX |
| PATTERN_PREPARED_ALIGNMENT | parent-to-prepared mapping | prepared parent mapping rate |
| EVIDENCE_SCOPE_MATRIX | determines allowed raw-pattern interpretation | branch-level scope |
| CANONICAL_2023_BASELINE | frozen baseline identity | repeatability hashes |
| OBSERVER_V1_MANIFEST | contract/runtime/schema identity | code SHA and data root |

## Mandatory Companions

Every Phase 2 dataset must carry or reference: `RUN_MANIFEST`, code SHA, runtime environment, fact-file SHA or stable business hash, and `evidence_scope`.

## Forbidden Inputs

- Old Phase 1C 909 ledger
- Local fact files without manifest/hash identity
- Unknown or unpinned project caches
- Optimization results
- Future counterfactual, AUDIT_REPLAY, or bare-branch facts mixed into MASTER_ACTUAL
- Online data replacing local hdata where local hdata covers the data type

## Analysis Boundary

Only branches marked `EXHAUSTIVE_RAW_PATTERN` may support direct full pre-prepared scan-filter EV. Branches marked `PREPARED_PARENT_ONLY` may support prepared-candidate attribution and actual-path lineage only; they cannot be used to estimate the complete raw universe or rejected-candidate EV.
