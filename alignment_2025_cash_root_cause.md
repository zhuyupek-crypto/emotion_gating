# 2025 Alignment Cash-Path Root Cause

Date: 2026-06-06

Scope: workspace copy only. No changes to `D:\work space\local_quant` or `D:\work space\hdata`.

## Current 2025 Result

Run result currently used:

- Directory: `rebuild_2025_warm2024_v16`
- JQ trades: 520
- Local trades: 505
- Matched by date/code/action: 484
- Missing: 36
- Extra: 21

The first 2025 missing pair is:

- 2025-03-10 buy `000678.XSHE`, followed by 2025-03-11 sell
- 2025-03-10 buy `603270.XSHG`, followed by 2025-03-11 sell

## Direct Cause For 2025-03-10

Local replay/instrumentation showed that on 2025-03-10:

- `000678.XSHE` and `603270.XSHG` both entered the local `rzq` pre-candidates.
- Both passed local daily open/yesterday-close filters.
- Both passed local call-auction imbalance scoring.
- Local had `held=1`, `slots=2`, `take=2`, so slots were available.
- Local did not place orders because `context.portfolio.available_cash` was only about 962 yuan.

So the 2025-03-10 mismatch is not a candidate-data or call-auction-data miss. It is a cash-path mismatch.

## Immediate Upstream Difference

On 2025-03-07, JQ and local had the same main candidates:

- `v227=14`
- `auction=31`
- `rzq=2`
- `zb=20`
- `bear=0`

But the auction sleeve differed:

- JQ: `auction_yiqian_daily_value = 10%`
- Local: `auction_yiqian_daily_value = 20%`

The code path is `_auction_yiqian_dynamic_value()`:

- strong sleeve 10% requires `core_wr >= 0.60` and `fb_pct >= 0.60`
- neutral sleeve 20% requires `core_wr >= 0.55` and `fb_pct >= 0.50`

On 2025-03-07:

- JQ: `core_wr=0.6167`, `recent_wr=0.5333`
- Local: `core_wr=0.58`, `recent_wr=0.50`

Therefore JQ selected 10%, local selected 20%. Local bought a larger `600133.XSHG` auction position, leaving insufficient cash on 2025-03-10.

## Earliest 2025 State Divergence

The first 2025 candidate differences occur immediately:

- 2025-01-02: JQ `auction=10`, `zb=13`; local `auction=9`, `zb=11`
- 2025-01-03: JQ `yjj=14`; local `yjj=13`

The first 2025 win-rate difference occurs on 2025-01-06:

- JQ: `core_wr=0.5667`
- Local: `core_wr=0.55`

On 2025-01-03 both systems sold `002345.XSHE` as a profitable `zb` trade. Since both recorded a win, the 2025-01-06 core win-rate divergence means the rolling 60-core-trade deque already had a different oldest element before the Jan 3 sell was appended.

## Warm-State Finding

The current 2025 run uses warm start at 2024. That does not reproduce JQ's pre-2024 carried state:

- JQ has live state and positions entering 2024, including a 2024-01-02 sell from a 2023 entry.
- Local `warm2024` starts without those pre-2024 positions and rolling trade deques.

Evidence from 2024 status comparison:

- 2024 common status days: 242
- core/recent win-rate differences: 204 days
- auction sleeve differences: 164 days
- candidate-count differences: 159 days

So the current 2025 mismatch is inherited from an incomplete 2024 warm state, then amplified through dynamic sleeve sizing and cash availability.

## Important Guardrail

Do not fix 2025-03-10 by hardcoding `000678.XSHE` / `603270.XSHG`, forcing the sleeve to 10%, or lowering the 0.60 threshold. The evidence points to upstream rolling-state/cash inheritance, not a true 2025 stock-specific exception.

Reasonable next directions:

- Align or reproduce the pre-2024 state before judging 2025 exactness.
- Build a project-local state preprocessor/cache that can warm rolling deques and positions efficiently.
- Continue 2024 mismatch localization only if exact 2025/2026 parity remains required.
