# Phase 2A Report

Conclusion: `PASS_ACTUAL_BASELINE`

`MASTER_ACTUAL_CONTRIBUTION_BASELINE`: actual 2023 motherboard contribution and resource competition only. This is not an independent branch run, standalone branch return, or counterfactual result.

## Final Summary

- Branch: `codex/motherboard-attribution-phase2a-actual-v1`
- Commit: `21670f76aede63842225634d206c6fcd6bd1186d`
- Draft PR: `pending`

- input signal hash: `2fee8ab8eb581a3a58c991bdbdb0bab5a47d18d0139464232a2d78f9025bf920`
- input terminal hash: `318db96161b34ac1fa423cb34e4dc5da174cf073412deda6c76cd35ca236df0a`
- input source hash: `95b278b5f89076aeb8150a9ec1d651309416bc6c281d7914d9a697606ff0f5ec`

- SIGNAL_EVENT: `2524`
- actual orders: `259`
- actual trade records: `259`
- buy lots: `132`
- year-end open lots: `1`

- portfolio net change: `258307.590000`
- attributed net change: `258307.590000`
- reconciliation residual: `0.000000001106`

## Branch ACTUAL_CONTRIBUTION
- Auction: `90499.388083`; prepared `1442`, filled `47`, fill rate `0.0326`
- YJJ: `-92863.088083`; prepared `125`, filled `37`, fill rate `0.2960`
- Scorpion: `104052.730000`; prepared `632`, filled `11`, fill rate `0.0174`
- RZQ: `-96616.300000`; prepared `46`, filled `7`, fill rate `0.1522`
- ZB: `253234.860000`; prepared `279`, filled `30`, fill rate `0.1075`

- actual contribution rank 1: `ZB` `253234.860000`
- actual contribution rank 2: `Scorpion` `104052.730000`
- largest prepared signal branch: `Auction` `1442`
- highest actual buy conversion branch: `YJJ` `0.2960`
- largest Slots blocked branch: `ZB` `63`
- largest cash blocked branch: `ZB` `38`

## Resource And Overlap Facts

- cross-branch overlap matrix event-pair count: `183`
- explicit blocking identity events: `3`
- resource-state-only blocking events: `169`

## Guardrails

- unfilled candidate future return calculations: `0`
- counterfactual runs: `0`
- optimization experiments: `0`

Can answer: actual branch PnL, actual opportunity occupation, terminal/resource states, branch overlaps, months, and motherboard state contribution in the 2023 actual run.

Cannot answer yet: branch native alpha, no-gate value, slots expansion value, handler order changes, or remove-one-branch portfolio effects.

Allowed next stage: branch native counterfactual only after this MASTER_ACTUAL baseline is accepted.

