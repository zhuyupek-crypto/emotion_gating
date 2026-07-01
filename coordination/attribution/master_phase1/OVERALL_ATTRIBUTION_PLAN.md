# Motherboard Attribution Overall Plan

This project is a causal decomposition of an already-evolved strategy system. It is not a parameter search, strategy optimization, or attempt to improve short-term backtest results.

The motherboard is treated as an opaque multi-expert system:

```text
market data
  -> emotion and market state
  -> branch routing and risk gates
  -> YJJ / Scorpion / RZQ / ZB / Auction
  -> ranking, slots, cash competition, orders, fills, exits
```

The purpose is to build a factual audit trail that answers where alpha, risk, and opportunity loss actually come from.

## Core Questions

```text
Which branch generated each signal?
Which signals were seen by the motherboard?
Which signals passed branch-native filters?
Which signals were blocked by motherboard gates?
Which signals passed gates but lost ranking, slots, cash, or order execution?
Which trades map back to one unique branch signal?
Which exits map back to the original entry signal?
What was the branch-native counterfactual outcome of filtered or displaced signals?
How do these answers change across market and emotion states?
```

## Principles

1. Observe at the source. Do not reconstruct raw signals only from final trade logs.
2. Separate alpha, routing, resources, and execution.
3. Preserve strategy behavior. Observer code must not mutate strategy state, candidates, slots, cash, orders, or matching.
4. Do not guess branch identity. Preserve `signal_id -> order_id -> trade_id -> branch`.
5. Use branch-native rules for counterfactuals. Do not score all missed trades with a universal next-day close return.

## Research Layers

```text
Alpha layer: YJJ / Scorpion / RZQ / ZB / Auction
Emotion layer: market_mode, raw_market_mode, active, FB, fb_pct, heat, momentum, stress
Routing/resource layer: enable flags, ranking, slots, cash, positions, pending orders
Risk/execution layer: stop loss, cooldowns, forced clearing, auction timing, limit states, slippage
```

## Phase Roadmap

```text
Phase 0: inventory, call-chain audit, observability gap, schema design
Phase 1: minimal motherboard observer smoke test, 2023-01-01 to 2023-03-31
Phase 2: full-year validation
Phase 3: branch-native counterfactuals
Phase 4: formal 2018-2025 matrices
Phase 5: later strategy redesign, only after facts are stable
```

Phase 0 and Phase 1 must not modify gates, delete branches, adjust slots, reallocate capital, change emotion state logic, introduce ranking models, or submit production strategy code.
