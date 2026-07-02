# Known Limitations

- The independent emotion panel is not connected in Observer v1.0; `emotion_*` fields are empty.
- `market_mode` is runtime strategy state, not an independent emotion model output.
- Several branches have `PREPARED_PARENT_ONLY` evidence. RAW_PATTERN_EVENT must not be interpreted as an exhaustive rejected raw universe unless the evidence matrix says `EXHAUSTIVE_RAW_PATTERN`.
- Phase 1 validates the 2023 full year only. The 2018-2025 formal matrix has not been run under this contract.
- Bare-branch counterfactual execution is not connected.
- Current facts are `MASTER_ACTUAL`; they are not counterfactual returns after hypothetical signal release.
- The old Phase 1C 909-signal artifact is `SUPERSEDED_FOR_ATTRIBUTION` and forbidden as Phase 2 input.
- Full parquet facts are local under `master_phase1e/full_year_run/`; future execution must rely on manifest and hash validation before use.
