# Auction Cache Generator Logic

- Generator: `build_auction_yiqian_prepare(year, hdata_root, cache_root, ipo_days=250, candidate_cap=40)`.
- Inputs: local hdata daily pivots `open`, `close`, `high`, `high_limit`, `money`, `volume`; security universe from `DataAPI.get_all_securities`.
- Target date T uses T-1, T-2, T-3 and T-4 daily data only.
- Universe: 60/00 stocks, non-ST/non-delisted by display name, IPO age at least 250 calendar days.
- `y2`: T-1 close at limit, T-2/T-3 not ever-limit, `avg_raw * 1.1 - 1 >= 0.07`, T-1 money in [5e8, 20e8], `inc4 <= 0.25`.
- `rzq`: T-1 ever-limit but not close-limit, T-2 not close-limit, not y2, `avg_raw - 1 >= -0.04`, T-1 money in [3e8, 19e8], close/open >= -5%, `inc4 <= 0.18`.
- Ranking: y2 before rzq, then descending T-1 money; capped at `candidate_cap` rows per date.
- `left_ok`: recomputed from historical highs/volumes through `_auction_yiqian_batch_left_pressure_api`.
- Output: `cache_root/auction_yiqian_prepare/{year}.parquet`.

This is a prepared-candidate cache, not a raw auction pattern hit.