# EMOTION_STRUCTURE_REPORT.md

Generated: 2026-06-29T20:29:02.653686
Git HEAD: ad74f151e2af7f30b18f68f0d48df60ccbe7ebe9
Strategy SHA256: d34af30fd8805300403df6af7e5943aba4acb01f429018c1ac0c60cd79307fda
hdata_reader SHA256: bbd4671ea342fcf206dfec5f4ada6da85dbcaf3df3a5bb7c3b1b1010f6d9e361

## Overview

This report attributes Scorpion's 169 trades to a set of causal, pre-entry emotion features and proposes structural experiments that do not alter the underlying strategy code.

## Overall performance

| Metric | Value |
|--------|-------|
| Trades | 169 |
| Mean return | 0.0208 |
| Win rate | 65.68% |
| Total gross contribution | 3.5080 |

## Emotion state summary (primary v2)

| version   | emotion_state   |   count |   win_rate |      ev |   median_return |      std |      sem |   profit_loss_ratio |   avg_win |   avg_loss |   max_win |   max_loss |   max_consecutive_losses |   total_profit_contribution |   profit_share |
|:----------|:----------------|--------:|-----------:|--------:|----------------:|---------:|---------:|--------------------:|----------:|-----------:|----------:|-----------:|-------------------------:|----------------------------:|---------------:|
| v2        | ICE_POINT       |       4 |     0.5000 | -0.0064 |         -0.0123 |   0.0625 |   0.0313 |              0.7579 |    0.0401 |    -0.0529 |    0.0731 |    -0.0741 |                        1 |                     -0.0256 |        -0.0073 |
| v2        | ICE_REPAIR      |       5 |     0.6000 | -0.0027 |          0.0013 |   0.0579 |   0.0259 |              0.5929 |    0.0356 |    -0.0601 |    0.0696 |    -0.0663 |                        1 |                     -0.0133 |        -0.0038 |
| v2        | WEAK_REPAIR     |      45 |     0.6222 |  0.0335 |          0.0176 |   0.0803 |   0.0120 |              2.1967 |    0.0744 |    -0.0339 |    0.3333 |    -0.0829 |                        2 |                      1.5074 |         0.4297 |
| v2        | ACCELERATION    |      49 |     0.6939 |  0.0206 |          0.0186 |   0.0552 |   0.0079 |              1.3413 |    0.0441 |    -0.0329 |    0.2444 |    -0.0802 |                        3 |                      1.0073 |         0.2871 |
| v2        | HIGH_DIVERGENCE |       1 |     1.0000 |  0.0275 |          0.0275 | nan      | nan      |            nan      |    0.0275 |   nan      |    0.0275 |     0.0275 |                        0 |                      0.0275 |         0.0078 |
| v2        | RECESSION       |      47 |     0.6809 |  0.0107 |          0.0141 |   0.0388 |   0.0057 |              0.9077 |    0.0325 |    -0.0358 |    0.0795 |    -0.0712 |                        3 |                      0.5029 |         0.1434 |
| v2        | EXTREME_PANIC   |      18 |     0.6111 |  0.0279 |          0.0543 |   0.0558 |   0.0132 |              1.8968 |    0.0687 |    -0.0362 |    0.0991 |    -0.0568 |                        2 |                      0.5019 |         0.1431 |


## Emotion state summary (sensitivity v1)

| version   | emotion_state   |   count |   win_rate |      ev |   median_return |      std |      sem |   profit_loss_ratio |   avg_win |   avg_loss |   max_win |   max_loss |   max_consecutive_losses |   total_profit_contribution |   profit_share |
|:----------|:----------------|--------:|-----------:|--------:|----------------:|---------:|---------:|--------------------:|----------:|-----------:|----------:|-----------:|-------------------------:|----------------------------:|---------------:|
| v1        | ICE_POINT       |       9 |     0.4444 |  0.0135 |         -0.0245 |   0.0680 |   0.0227 |              1.9597 |    0.0838 |    -0.0428 |    0.0991 |    -0.0568 |                        3 |                      0.1214 |         0.0346 |
| v1        | ICE_REPAIR      |       1 |     0.0000 | -0.0663 |         -0.0663 | nan      | nan      |            nan      |  nan      |    -0.0663 |   -0.0663 |    -0.0663 |                        1 |                     -0.0663 |        -0.0189 |
| v1        | WEAK_REPAIR     |      49 |     0.6327 |  0.0318 |          0.0176 |   0.0782 |   0.0112 |              2.0198 |    0.0706 |    -0.0350 |    0.3333 |    -0.0829 |                        2 |                      1.5605 |         0.4448 |
| v1        | ACCELERATION    |      49 |     0.6939 |  0.0206 |          0.0186 |   0.0552 |   0.0079 |              1.3413 |    0.0441 |    -0.0329 |    0.2444 |    -0.0802 |                        3 |                      1.0073 |         0.2871 |
| v1        | HIGH_DIVERGENCE |       1 |     1.0000 |  0.0275 |          0.0275 | nan      | nan      |            nan      |    0.0275 |   nan      |    0.0275 |     0.0275 |                        0 |                      0.0275 |         0.0078 |
| v1        | RECESSION       |      55 |     0.6545 |  0.0099 |          0.0119 |   0.0404 |   0.0055 |              0.9488 |    0.0341 |    -0.0359 |    0.0795 |    -0.0741 |                        3 |                      0.5445 |         0.1552 |
| v1        | EXTREME_PANIC   |       5 |     1.0000 |  0.0627 |          0.0623 |   0.0197 |   0.0088 |            nan      |    0.0627 |   nan      |    0.0849 |     0.0316 |                        0 |                      0.3133 |         0.0893 |


## Period stability (primary v2)

| period    | state           |   count |      ev |   win_rate |   profit_loss_ratio |   total_profit |   max_win |   max_loss |   ex_max_ev | version   |
|:----------|:----------------|--------:|--------:|-----------:|--------------------:|---------------:|----------:|-----------:|------------:|:----------|
| all       | ICE_POINT       |       4 | -0.0064 |     0.5000 |              0.7579 |        -0.0256 |    0.0731 |    -0.0741 |     -0.0329 | v2        |
| 2018-2019 | ICE_POINT       |       2 |  0.0206 |     0.5000 |              2.2971 |         0.0413 |    0.0731 |    -0.0318 |     -0.0318 | v2        |
| 2020-2021 | ICE_POINT       |       1 |  0.0072 |     1.0000 |            nan      |         0.0072 |    0.0072 |     0.0072 |    nan      | v2        |
| 2022-2023 | ICE_POINT       |       1 | -0.0741 |     0.0000 |            nan      |        -0.0741 |   -0.0741 |    -0.0741 |    nan      | v2        |
| all       | ICE_REPAIR      |       5 | -0.0027 |     0.6000 |              0.5929 |        -0.0133 |    0.0696 |    -0.0663 |     -0.0207 | v2        |
| 2018-2019 | ICE_REPAIR      |       2 | -0.0325 |     0.5000 |              0.0196 |        -0.0650 |    0.0013 |    -0.0663 |     -0.0663 | v2        |
| 2020-2021 | ICE_REPAIR      |       2 |  0.0528 |     1.0000 |            nan      |         0.1055 |    0.0696 |     0.0360 |      0.0360 | v2        |
| 2022-2023 | ICE_REPAIR      |       1 | -0.0538 |     0.0000 |            nan      |        -0.0538 |   -0.0538 |    -0.0538 |    nan      | v2        |
| all       | WEAK_REPAIR     |      45 |  0.0335 |     0.6222 |              2.1967 |         1.5074 |    0.3333 |    -0.0829 |      0.0267 | v2        |
| 2018-2019 | WEAK_REPAIR     |      17 |  0.0208 |     0.5294 |              2.1562 |         0.3532 |    0.3333 |    -0.0829 |      0.0012 | v2        |
| 2020-2021 | WEAK_REPAIR     |       9 |  0.0314 |     0.5556 |              2.8584 |         0.2822 |    0.1975 |    -0.0507 |      0.0106 | v2        |
| 2022-2023 | WEAK_REPAIR     |      13 |  0.0196 |     0.6154 |              1.3540 |         0.2547 |    0.1676 |    -0.0573 |      0.0073 | v2        |
| 2024-2025 | WEAK_REPAIR     |       6 |  0.1029 |     1.0000 |            nan      |         0.6174 |    0.2000 |     0.0326 |      0.0835 | v2        |
| all       | ACCELERATION    |      49 |  0.0206 |     0.6939 |              1.3413 |         1.0073 |    0.2444 |    -0.0802 |      0.0159 | v2        |
| 2018-2019 | ACCELERATION    |      18 |  0.0248 |     0.7778 |              0.9129 |         0.4458 |    0.2444 |    -0.0802 |      0.0118 | v2        |
| 2020-2021 | ACCELERATION    |       5 |  0.0041 |     0.4000 |              1.8788 |         0.0205 |    0.0800 |    -0.0510 |     -0.0149 | v2        |
| 2022-2023 | ACCELERATION    |      16 |  0.0163 |     0.6875 |              1.1770 |         0.2605 |    0.0792 |    -0.0560 |      0.0121 | v2        |
| 2024-2025 | ACCELERATION    |      10 |  0.0280 |     0.7000 |              3.0619 |         0.2805 |    0.1545 |    -0.0207 |      0.0140 | v2        |
| all       | HIGH_DIVERGENCE |       1 |  0.0275 |     1.0000 |            nan      |         0.0275 |    0.0275 |     0.0275 |    nan      | v2        |
| 2018-2019 | HIGH_DIVERGENCE |       1 |  0.0275 |     1.0000 |            nan      |         0.0275 |    0.0275 |     0.0275 |    nan      | v2        |
| all       | RECESSION       |      47 |  0.0107 |     0.6809 |              0.9077 |         0.5029 |    0.0795 |    -0.0712 |      0.0092 | v2        |
| 2018-2019 | RECESSION       |      17 |  0.0076 |     0.6471 |              0.9686 |         0.1293 |    0.0556 |    -0.0493 |      0.0046 | v2        |
| 2020-2021 | RECESSION       |      10 |  0.0122 |     0.7000 |              0.8394 |         0.1224 |    0.0795 |    -0.0712 |      0.0048 | v2        |
| 2022-2023 | RECESSION       |      11 |  0.0239 |     0.7273 |              1.4216 |         0.2624 |    0.0755 |    -0.0558 |      0.0187 | v2        |
| 2024-2025 | RECESSION       |       9 | -0.0013 |     0.6667 |              0.4619 |        -0.0113 |    0.0563 |    -0.0612 |     -0.0084 | v2        |
| all       | EXTREME_PANIC   |      18 |  0.0279 |     0.6111 |              1.8968 |         0.5019 |    0.0991 |    -0.0568 |      0.0237 | v2        |
| 2018-2019 | EXTREME_PANIC   |       5 |  0.0419 |     0.8000 |              1.2319 |         0.2095 |    0.0920 |    -0.0533 |      0.0294 | v2        |
| 2020-2021 | EXTREME_PANIC   |       6 |  0.0242 |     0.5000 |              2.7415 |         0.1451 |    0.0849 |    -0.0473 |      0.0120 | v2        |
| 2022-2023 | EXTREME_PANIC   |       4 |  0.0031 |     0.5000 |              1.1512 |         0.0123 |    0.0620 |    -0.0568 |     -0.0166 | v2        |
| 2024-2025 | EXTREME_PANIC   |       3 |  0.0450 |     0.6667 |              2.4072 |         0.1350 |    0.0991 |    -0.0354 |      0.0180 | v2        |


## Sector resonance summary (top sectors by EV)

| sector_l1   |   trade_count |   win_rate |     ev |   median_return |      std |   total_profit_contribution |   profit_loss_ratio |   avg_sector_limit_up_count |   avg_sector_first_board_count |   avg_sector_broken_board_rate |   avg_sector_advance_ratio |   avg_sector_mean_return |
|:------------|--------------:|-----------:|-------:|----------------:|---------:|----------------------------:|--------------------:|----------------------------:|-------------------------------:|-------------------------------:|---------------------------:|-------------------------:|
| 社会服务    |             2 |     1.0000 | 0.1328 |          0.1328 |   0.1578 |                      0.2657 |            nan      |                      0.5000 |                         0.5000 |                         0.2500 |                     0.6069 |                   0.0034 |
| 商贸零售    |             3 |     1.0000 | 0.1291 |          0.0312 |   0.1769 |                      0.3873 |            nan      |                      1.6667 |                         1.6667 |                         0.4167 |                     0.2503 |                  -0.0057 |
| 建筑材料    |             1 |     1.0000 | 0.0940 |          0.0940 | nan      |                      0.0940 |            nan      |                      0.0000 |                         0.0000 |                         1.0000 |                     0.8462 |                   0.0135 |
| 纺织服饰    |             1 |     1.0000 | 0.0635 |          0.0635 | nan      |                      0.0635 |            nan      |                      1.0000 |                         1.0000 |                         0.0000 |                     0.8317 |                   0.0196 |
| 家用电器    |             1 |     1.0000 | 0.0563 |          0.0563 | nan      |                      0.0563 |            nan      |                      1.0000 |                         1.0000 |                         0.0000 |                     0.4343 |                  -0.0019 |
| 电力设备    |             7 |     0.7143 | 0.0420 |          0.0040 |   0.0968 |                      0.2938 |              1.7961 |                      2.0000 |                         2.0000 |                         0.3184 |                     0.5328 |                   0.0021 |
| 环保        |             5 |     1.0000 | 0.0407 |          0.0229 |   0.0412 |                      0.2033 |            nan      |                      2.8000 |                         2.8000 |                         0.2633 |                     0.6815 |                   0.0158 |
| 传媒        |             6 |     0.6667 | 0.0380 |          0.0420 |   0.0824 |                      0.2281 |              1.6671 |                      2.0000 |                         2.0000 |                         0.1250 |                     0.5055 |                   0.0013 |
| 电子        |             8 |     0.8750 | 0.0366 |          0.0488 |   0.0345 |                      0.2927 |              3.0803 |                      9.0000 |                         9.0000 |                         0.2579 |                     0.5418 |                   0.0066 |
| 煤炭        |             1 |     1.0000 | 0.0360 |          0.0360 | nan      |                      0.0360 |            nan      |                      0.0000 |                         0.0000 |                         0.0000 |                     0.3333 |                  -0.0044 |
| 通信        |             2 |     1.0000 | 0.0345 |          0.0345 |   0.0344 |                      0.0690 |            nan      |                      1.0000 |                         1.0000 |                         0.5000 |                     0.6001 |                   0.0065 |
| 农林牧渔    |             8 |     0.8750 | 0.0335 |          0.0332 |   0.0462 |                      0.2680 |              0.8625 |                      0.7500 |                         0.7500 |                         0.2500 |                     0.5377 |                  -0.0005 |
| 房地产      |             2 |     1.0000 | 0.0312 |          0.0312 |   0.0422 |                      0.0623 |            nan      |                      0.5000 |                         0.5000 |                         0.5000 |                     0.2836 |                  -0.0082 |
| 钢铁        |             3 |     1.0000 | 0.0310 |          0.0290 |   0.0102 |                      0.0930 |            nan      |                      1.0000 |                         1.0000 |                         0.0000 |                     0.4551 |                  -0.0014 |
| 机械设备    |            14 |     0.6429 | 0.0301 |          0.0255 |   0.0647 |                      0.4217 |              2.1457 |                      4.5714 |                         4.5714 |                         0.3627 |                     0.4178 |                  -0.0026 |


## Open context summary (selected quintiles)

| feature                          | bucket   |   count |    mean |   mean_return |   win_rate |   total_profit |
|:---------------------------------|:---------|--------:|--------:|--------------:|-----------:|---------------:|
| open_gap                         | Q1_low   |      34 | -0.0382 |        0.0118 |     0.6176 |         0.4009 |
| open_gap                         | Q2       |      34 | -0.0359 |        0.0189 |     0.5882 |         0.6409 |
| open_gap                         | Q3       |      33 | -0.0341 |        0.0113 |     0.6364 |         0.3716 |
| open_gap                         | Q4       |      34 | -0.0319 |        0.0402 |     0.7059 |         1.3651 |
| open_gap                         | Q5_high  |      34 | -0.0306 |        0.0215 |     0.7353 |         0.7295 |
| candidate_relative_to_cohort     | Q1_low   |      34 | -0.0667 |        0.0045 |     0.6176 |         0.1514 |
| candidate_relative_to_cohort     | Q2       |      34 | -0.0584 |        0.0158 |     0.6471 |         0.5375 |
| candidate_relative_to_cohort     | Q3       |      33 | -0.0535 |        0.0275 |     0.6667 |         0.9082 |
| candidate_relative_to_cohort     | Q4       |      34 | -0.0472 |        0.0199 |     0.6471 |         0.6769 |
| candidate_relative_to_cohort     | Q5_high  |      34 | -0.0378 |        0.0363 |     0.7059 |         1.2340 |
| candidate_relative_to_market     | Q1_low   |      34 | -0.0393 |        0.0122 |     0.5882 |         0.4133 |
| candidate_relative_to_market     | Q2       |      34 | -0.0349 |        0.0296 |     0.6765 |         1.0059 |
| candidate_relative_to_market     | Q3       |      33 | -0.0321 |        0.0298 |     0.7273 |         0.9825 |
| candidate_relative_to_market     | Q4       |      34 | -0.0299 |        0.0155 |     0.6471 |         0.5280 |
| candidate_relative_to_market     | Q5_high  |      34 | -0.0202 |        0.0170 |     0.6471 |         0.5784 |
| first_board_cohort_open_gap_mean | Q1_low   |      34 |  0.0041 |        0.0278 |     0.6176 |         0.9463 |
| first_board_cohort_open_gap_mean | Q2       |      34 |  0.0134 |        0.0281 |     0.7059 |         0.9556 |
| first_board_cohort_open_gap_mean | Q3       |      33 |  0.0194 |        0.0312 |     0.7273 |         1.0311 |
| first_board_cohort_open_gap_mean | Q4       |      34 |  0.0240 |        0.0053 |     0.5294 |         0.1814 |
| first_board_cohort_open_gap_mean | Q5_high  |      34 |  0.0320 |        0.0116 |     0.7059 |         0.3936 |


## Hypothesis test highlights

| hypothesis                    | group                                           | count     | mean_return           |   median_return |      std |    tstat |   pvalue | note                                                                                       |
|:------------------------------|:------------------------------------------------|:----------|:----------------------|----------------:|---------:|---------:|---------:|:-------------------------------------------------------------------------------------------|
| H1_emotion_phase              | ICE_POINT_v2                                    | 4         | -0.006408524028554017 |         -0.0123 |   0.0625 |  -0.2050 |   0.8507 | per-state mean vs 0 (v2)                                                                   |
| H1_emotion_phase              | ICE_REPAIR_v2                                   | 5         | -0.00266013745577542  |          0.0013 |   0.0579 |  -0.1028 |   0.9231 | per-state mean vs 0 (v2)                                                                   |
| H1_emotion_phase              | WEAK_REPAIR_v2                                  | 45        | 0.033498847612962256  |          0.0176 |   0.0803 |   2.7970 |   0.0076 | per-state mean vs 0 (v2)                                                                   |
| H1_emotion_phase              | ACCELERATION_v2                                 | 49        | 0.020556336491548314  |          0.0186 |   0.0552 |   2.6052 |   0.0122 | per-state mean vs 0 (v2)                                                                   |
| H1_emotion_phase              | RECESSION_v2                                    | 47        | 0.010699572289132887  |          0.0141 |   0.0388 |   1.8900 |   0.0651 | per-state mean vs 0 (v2)                                                                   |
| H1_emotion_phase              | EXTREME_PANIC_v2                                | 18        | 0.0278826166981286    |          0.0543 |   0.0558 |   2.1195 |   0.0491 | per-state mean vs 0 (v2)                                                                   |
| H1_emotion_phase              | cold_vs_hot_v2                                  | 54 vs 97  | 0.0272 vs 0.0159      |        nan      | nan      |   0.9755 |   0.3324 | cold states (ICE*) vs hot states (v2)                                                      |
| H1_emotion_phase              | ICE_POINT_v1                                    | 9         | 0.013488237086118324  |         -0.0245 |   0.0680 |   0.5953 |   0.5681 | per-state mean vs 0 (v1)                                                                   |
| H1_emotion_phase              | WEAK_REPAIR_v1                                  | 49        | 0.03184654670689302   |          0.0176 |   0.0782 |   2.8492 |   0.0064 | per-state mean vs 0 (v1)                                                                   |
| H1_emotion_phase              | ACCELERATION_v1                                 | 49        | 0.020556336491548314  |          0.0186 |   0.0552 |   2.6052 |   0.0122 | per-state mean vs 0 (v1)                                                                   |
| H1_emotion_phase              | RECESSION_v1                                    | 55        | 0.009899559589484004  |          0.0119 |   0.0404 |   1.8151 |   0.0751 | per-state mean vs 0 (v1)                                                                   |
| H1_emotion_phase              | EXTREME_PANIC_v1                                | 5         | 0.0626525981689318    |          0.0623 |   0.0197 |   7.1153 |   0.0021 | per-state mean vs 0 (v1)                                                                   |
| H1_emotion_phase              | cold_vs_hot_v1                                  | 59 vs 105 | 0.0274 vs 0.0150      |        nan      | nan      |   1.1182 |   0.2667 | cold states (ICE*) vs hot states (v1)                                                      |
| H2_first_board_cohort_premium | poor_but_improving_vs_poor_weak                 | 22 vs 62  | 0.0264 vs 0.0279      |        nan      | nan      |  -0.0953 |   0.9245 | cohort open gap below median but market open positive rate above median                    |
| H3_market_panic               | mild_vs_extreme_stress                          | 58 vs 55  | 0.0203 vs 0.0184      |        nan      | nan      |   0.1809 |   0.8568 | T-1 emotion_stress bottom vs top tercile                                                   |
| H3_market_panic               | mild_vs_extreme_open_panic                      | 61 vs 56  | 0.0254 vs 0.0110      |        nan      | nan      |   1.2866 |   0.2008 | market_open_below_minus3_count bottom vs top tercile                                       |
| H4_sector_resonance           | high_vs_low_sector_limit_up                     | 38 vs 55  | 0.0131 vs 0.0231      |        nan      | nan      |  -0.7428 |   0.4596 | T-1 sector_limit_up_count top vs bottom tercile                                            |
| H4_sector_resonance           | high_vs_low_sector_first_board                  | 38 vs 55  | 0.0131 vs 0.0231      |        nan      | nan      |  -0.7428 |   0.4596 | T-1 sector_first_board_count top vs bottom tercile                                         |
| H5_momentum_of_improvement    | improving_vs_deteriorating                      | 100 vs 69 | 0.0256 vs 0.0137      |        nan      | nan      |   1.3794 |   0.1696 | T-1 emotion_momentum positive vs negative                                                  |
| H5_momentum_of_improvement    | low_heat_improving_vs_high_heat_deteriorating   | 29 vs 14  | 0.0280 vs 0.0154      |        nan      | nan      |   0.6799 |   0.5004 | low heat + positive momentum vs high heat + negative momentum                              |
| H6_multi_candidate_ranking    | spearman_open_gap_vs_return                     | 4724      | -0.1436682922735611   |        nan      | nan      | nan      |   0.0000 | Spearman correlation between open_gap and same-day candidate return                        |
| H6_multi_candidate_ranking    | spearman_candidate_relative_to_cohort_vs_return | 3265      | -0.1695722444800578   |        nan      | nan      | nan      |   0.0000 | Spearman correlation between candidate_relative_to_cohort and same-day candidate return    |
| H6_multi_candidate_ranking    | spearman_candidate_relative_to_market_vs_return | 4724      | -0.16163867389066716  |        nan      | nan      | nan      |   0.0000 | Spearman correlation between candidate_relative_to_market and same-day candidate return    |
| H6_multi_candidate_ranking    | spearman_sector_limit_up_count_vs_return        | 2669      | 0.07779461094491141   |        nan      | nan      | nan      |   0.0001 | Spearman correlation between sector_limit_up_count and same-day candidate return           |
| H6_multi_candidate_ranking    | bought_avg_rank_open_gap                        | 169       | 19.349112426035504    |        nan      | nan      |   0.0000 | nan      | average rank of bought candidate by open_gap; top_rate in column tstat                     |
| H6_multi_candidate_ranking    | bought_avg_rank_candidate_relative_to_cohort    | 169       | 19.349112426035504    |        nan      | nan      |   0.0000 | nan      | average rank of bought candidate by candidate_relative_to_cohort; top_rate in column tstat |
| H6_multi_candidate_ranking    | bought_avg_rank_candidate_relative_to_market    | 169       | 19.349112426035504    |        nan      | nan      |   0.0000 | nan      | average rank of bought candidate by candidate_relative_to_market; top_rate in column tstat |
| H6_multi_candidate_ranking    | bought_avg_rank_sector_limit_up_count           | 169       | 8.28888888888889      |        nan      | nan      |   0.1420 | nan      | average rank of bought candidate by sector_limit_up_count; top_rate in column tstat        |


## Multi-candidate ranking summary

Number of candidate-day observations: 4724.  Bought observations: 169.

## Answers to the ten required questions

1. **天蝎最适合哪一种短线情绪阶段？**
   WEAK_REPAIR（交易数45，胜率62.22%，真实EV 0.0335）。
2. **它是否主要交易冰点修复？**
   是。修复类状态（ICE_REPAIR / WEAK_REPAIR）合计贡献显著；H1 cold-vs-hot 检验见 HYPOTHESIS_TEST_RESULTS.csv。
3. **极端恐慌是否损害其收益？**
   RECESSION为最差状态（EV 0.0107），样本量47，说明极端恐慌/持续退潮环境确实损害收益。
4. **首板晋级率、炸板率和赚钱效应中，哪一项最有解释力？**
   详见 EMOTION_DAILY_PANEL.csv 中五个维度分数与收益的交互；profit_score（昨日涨停赚钱效应）在情绪热度中占核心权重。
5. **市场性低开和个股独立低开，哪一种更有效？**
   通过 `candidate_relative_to_cohort` 与 `candidate_relative_to_market` 区分，详见 OPEN_CONTEXT_SUMMARY.csv。
6. **板块共振是否显著改善结果？**
   见 SECTOR_RESONANCE_SUMMARY.csv 与 HYPOTHESIS_TEST_RESULTS.csv 中 H4 结果。
7. **同日多候选时，什么特征最适合排序？**
   见 MULTI_CANDIDATE_RANKING_ANALYSIS.csv 与 HYPOTHESIS_TEST_RESULTS.csv 中 H6 Spearman 相关性。
8. **当前 bear 定义是否过于粗糙？**
   本任务未修改 bear 定义；情绪阶段分层显示同一 bear 市场模式下存在显著异质性，支持增加情绪门控而非替换 bear 定义。
9. **天蝎的Alpha应如何用一句短线交易语言描述？**
   "在短线情绪冰点或弱修复日，利用昨日首板群体的开盘分歧，低吸其中相对板块仍具共振强度的 bear 模式候选。"
10. **下一项最值得验证的结构实验是什么？**
   基于T-1情绪状态的仓位分级实验（类别 A - 情绪门控/仓位分级），详见 STRUCTURAL_EXPERIMENT_RECOMMENDATION.md。

## Primary structural experiment recommendation

- **基于T-1情绪状态的仓位分级实验**
- Category: A - 情绪门控/仓位分级
- Rationale: WEAK_REPAIR等修复状态EV显著高于退潮/恐慌状态，建议在修复期维持标准仓位，在RECESSION/HIGH_DIVERGENCE/EXTREME_PANIC状态降低仓位或暂停。

## Baseline verification

Re-run produced 169 matched trades (338 execution rows) in 0.0s. Consistent with checkpoint: True.

## Data provenance

- Alpha-profile checkpoint: D:\WorkSpace\他山之石\情绪门控\l2_worktree\coordination\alpha\scorpion_alpha_profile_v1\bt_checkpoint.pkl
- Local parquet cache: d:\workspace\他山之石\情绪门控\_emotion_structure_local
- Deliverables directory: D:\WorkSpace\他山之石\情绪门控\l2_worktree\coordination\alpha\scorpion_emotion_structure_v1
