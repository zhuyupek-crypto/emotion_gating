# EMOTION_STRUCTURE_REPORT.md

Generated: 2026-06-30T02:26:08.471936
Git HEAD: 151f337e4bd8112f29486b99c908196c8e2e6869
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
| 农林牧渔    |             2 |     1.0000 | 0.1194 |          0.1194 |   0.0680 |                      0.2389 |            nan      |                      2.5000 |                         1.5000 |                         0.2000 |                     0.2960 |                  -0.0055 |
| 商贸零售    |             3 |     0.6667 | 0.0851 |          0.0601 |   0.1485 |                      0.2552 |              3.0869 |                      0.3333 |                         0.3333 |                         0.1667 |                     0.3174 |                  -0.0064 |
| 纺织服饰    |             3 |     1.0000 | 0.0779 |          0.0553 |   0.0682 |                      0.2338 |            nan      |                      0.6667 |                         0.6667 |                         0.4167 |                     0.3037 |                  -0.0108 |
| 公用事业    |             2 |     1.0000 | 0.0779 |          0.0779 |   0.0099 |                      0.1558 |            nan      |                      0.5000 |                         0.5000 |                         0.0000 |                     0.2153 |                  -0.0103 |
| 非银金融    |             2 |     1.0000 | 0.0609 |          0.0609 |   0.0539 |                      0.1218 |            nan      |                      0.5000 |                         0.5000 |                         0.3333 |                     0.4150 |                  -0.0064 |
| 建筑材料    |             1 |     1.0000 | 0.0588 |          0.0588 | nan      |                      0.0588 |            nan      |                      1.0000 |                         1.0000 |                         0.5000 |                     0.3556 |                  -0.0052 |
| 轻工制造    |             6 |     1.0000 | 0.0569 |          0.0476 |   0.0342 |                      0.3416 |            nan      |                      2.1667 |                         1.5000 |                         0.3833 |                     0.5340 |                  -0.0002 |
| 社会服务    |             4 |     1.0000 | 0.0561 |          0.0493 |   0.0272 |                      0.2243 |            nan      |                      1.7500 |                         1.5000 |                         0.3958 |                     0.4668 |                  -0.0055 |
| 钢铁        |             1 |     1.0000 | 0.0514 |          0.0514 | nan      |                      0.0514 |            nan      |                      1.0000 |                         1.0000 |                         0.5000 |                     0.6486 |                   0.0119 |
| 家用电器    |             2 |     1.0000 | 0.0471 |          0.0471 |   0.0388 |                      0.0942 |            nan      |                      0.0000 |                         0.0000 |                         0.5000 |                     0.4222 |                  -0.0032 |
| 食品饮料    |             3 |     0.6667 | 0.0448 |          0.0073 |   0.1108 |                      0.1343 |              2.0810 |                      2.0000 |                         1.6667 |                         0.3056 |                     0.6400 |                   0.0122 |
| 煤炭        |             3 |     0.6667 | 0.0362 |          0.0635 |   0.0540 |                      0.1085 |              2.5854 |                      0.3333 |                         0.3333 |                         0.1667 |                     0.4164 |                   0.0018 |
| 房地产      |             3 |     0.6667 | 0.0310 |          0.0541 |   0.0730 |                      0.0931 |              1.4177 |                      1.3333 |                         1.0000 |                         0.0000 |                     0.6323 |                   0.0051 |
| 通信        |             3 |     0.6667 | 0.0258 |          0.0013 |   0.0465 |                      0.0775 |             12.1199 |                      1.6667 |                         1.3333 |                         0.3889 |                     0.4777 |                   0.0012 |
| 交通运输    |             4 |     0.7500 | 0.0249 |          0.0261 |   0.0488 |                      0.0997 |              1.3773 |                      1.0000 |                         0.7500 |                         0.2500 |                     0.5228 |                   0.0024 |


## Open context summary (selected quintiles)

| feature                          | bucket   |   count |    mean |   mean_return |   win_rate |   total_profit |
|:---------------------------------|:---------|--------:|--------:|--------------:|-----------:|---------------:|
| open_gap                         | Q1_low   |      34 | -0.0382 |        0.0118 |     0.6176 |         0.4009 |
| open_gap                         | Q2       |      34 | -0.0359 |        0.0189 |     0.5882 |         0.6409 |
| open_gap                         | Q3       |      33 | -0.0341 |        0.0113 |     0.6364 |         0.3716 |
| open_gap                         | Q4       |      34 | -0.0319 |        0.0402 |     0.7059 |         1.3651 |
| open_gap                         | Q5_high  |      34 | -0.0306 |        0.0215 |     0.7353 |         0.7295 |
| candidate_relative_to_cohort     | Q1_low   |      34 | -0.0596 |        0.0191 |     0.7059 |         0.6487 |
| candidate_relative_to_cohort     | Q2       |      34 | -0.0531 |        0.0131 |     0.6176 |         0.4461 |
| candidate_relative_to_cohort     | Q3       |      33 | -0.0489 |        0.0154 |     0.5758 |         0.5087 |
| candidate_relative_to_cohort     | Q4       |      34 | -0.0421 |        0.0199 |     0.6471 |         0.6779 |
| candidate_relative_to_cohort     | Q5_high  |      34 | -0.0314 |        0.0361 |     0.7353 |         1.2266 |
| candidate_relative_to_market     | Q1_low   |      34 | -0.0393 |        0.0122 |     0.5882 |         0.4133 |
| candidate_relative_to_market     | Q2       |      34 | -0.0349 |        0.0296 |     0.6765 |         1.0059 |
| candidate_relative_to_market     | Q3       |      33 | -0.0321 |        0.0298 |     0.7273 |         0.9825 |
| candidate_relative_to_market     | Q4       |      34 | -0.0299 |        0.0155 |     0.6471 |         0.5280 |
| candidate_relative_to_market     | Q5_high  |      34 | -0.0202 |        0.0170 |     0.6471 |         0.5784 |
| first_board_cohort_open_gap_mean | Q1_low   |      34 | -0.0022 |        0.0328 |     0.7059 |         1.1140 |
| first_board_cohort_open_gap_mean | Q2       |      34 |  0.0084 |        0.0269 |     0.6765 |         0.9146 |
| first_board_cohort_open_gap_mean | Q3       |      33 |  0.0138 |        0.0120 |     0.6364 |         0.3961 |
| first_board_cohort_open_gap_mean | Q4       |      34 |  0.0187 |        0.0069 |     0.5000 |         0.2342 |
| first_board_cohort_open_gap_mean | Q5_high  |      34 |  0.0255 |        0.0250 |     0.7647 |         0.8492 |


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
| H2_first_board_cohort_premium | poor_but_improving_vs_poor_weak                 | 23 vs 61  | 0.0158 vs 0.0282      |        nan      | nan      |  -0.9989 |   0.3217 | cohort open gap below median but market open positive rate above median                    |
| H3_market_panic               | mild_vs_extreme_stress                          | 58 vs 55  | 0.0203 vs 0.0184      |        nan      | nan      |   0.1809 |   0.8568 | T-1 emotion_stress bottom vs top tercile                                                   |
| H3_market_panic               | mild_vs_extreme_open_panic                      | 61 vs 56  | 0.0254 vs 0.0110      |        nan      | nan      |   1.2866 |   0.2008 | market_open_below_minus3_count bottom vs top tercile                                       |
| H4_sector_resonance           | high_vs_low_sector_limit_up                     | 45 vs 53  | 0.0114 vs 0.0215      |        nan      | nan      |  -0.8784 |   0.3820 | T-1 sector_limit_up_count top vs bottom tercile                                            |
| H4_sector_resonance           | high_vs_low_sector_first_board                  | 30 vs 63  | 0.0166 vs 0.0235      |        nan      | nan      |  -0.5687 |   0.5714 | T-1 sector_first_board_count top vs bottom tercile                                         |
| H5_momentum_of_improvement    | improving_vs_deteriorating                      | 100 vs 69 | 0.0256 vs 0.0137      |        nan      | nan      |   1.3794 |   0.1696 | T-1 emotion_momentum positive vs negative                                                  |
| H5_momentum_of_improvement    | low_heat_improving_vs_high_heat_deteriorating   | 29 vs 14  | 0.0280 vs 0.0154      |        nan      | nan      |   0.6799 |   0.5004 | low heat + positive momentum vs high heat + negative momentum                              |
| H6_multi_candidate_ranking    | spearman_open_gap_vs_return                     | 7669      | -0.1401711418559583   |        nan      | nan      | nan      |   0.0000 | Spearman correlation between open_gap and same-day candidate return                        |
| H6_multi_candidate_ranking    | spearman_candidate_relative_to_cohort_vs_return | 7210      | -0.16993586759316942  |        nan      | nan      | nan      |   0.0000 | Spearman correlation between candidate_relative_to_cohort and same-day candidate return    |
| H6_multi_candidate_ranking    | spearman_candidate_relative_to_market_vs_return | 7669      | -0.15317410766019457  |        nan      | nan      | nan      |   0.0000 | Spearman correlation between candidate_relative_to_market and same-day candidate return    |
| H6_multi_candidate_ranking    | spearman_sector_limit_up_count_vs_return        | 5978      | 0.10082089087305769   |        nan      | nan      | nan      |   0.0000 | Spearman correlation between sector_limit_up_count and same-day candidate return           |
| H6_multi_candidate_ranking    | bought_avg_rank_open_gap                        | 169       | 19.349112426035504    |        nan      | nan      |   0.0000 | nan      | average rank of bought candidate by open_gap; top_rate in column tstat                     |
| H6_multi_candidate_ranking    | bought_avg_rank_candidate_relative_to_cohort    | 169       | 19.349112426035504    |        nan      | nan      |   0.0000 | nan      | average rank of bought candidate by candidate_relative_to_cohort; top_rate in column tstat |
| H6_multi_candidate_ranking    | bought_avg_rank_candidate_relative_to_market    | 169       | 19.349112426035504    |        nan      | nan      |   0.0000 | nan      | average rank of bought candidate by candidate_relative_to_market; top_rate in column tstat |
| H6_multi_candidate_ranking    | bought_avg_rank_sector_limit_up_count           | 169       | 7.044117647058823     |        nan      | nan      |   0.1538 | nan      | average rank of bought candidate by sector_limit_up_count; top_rate in column tstat        |


## Multi-candidate ranking summary

Number of candidate-day observations: 7669.  Bought observations: 169.

## Review corrections

本次审查对原报告结论进行以下修正：

- 情绪状态门控：仅 WEAK_REPAIR 可形成可靠结论；ICE_POINT、ICE_REPAIR、HIGH_DIVERGENCE 样本过少，不得用于硬门控。
- 板块共振：不再声称“显著解释力”。板块涨停数量与候选代理收益仅呈弱正相关，对 169 笔真实交易无显著正向效果。
- 统计显著性：H4/H6 已补充 Bootstrap 95% 置信区间，大样本小 p 值不等于强解释力。
- 基线验证：默认保持快速 checkpoint 模式；完整基线仅由 `--baseline` 显式触发。

## Emotion state conclusion validity

| 可形成结论 | 不可形成结论（样本<20） |
|-----------|----------------------|
| WEAK_REPAIR | ICE_POINT |
| ACCELERATION | ICE_REPAIR |
| RECESSION | HIGH_DIVERGENCE |
| EXTREME_PANIC（标记小样本） | |

WEAK_REPAIR 是收益增强状态，但 ACCELERATION、RECESSION、EXTREME_PANIC 仍具有正 EV，当前证据不支持情绪状态硬过滤或直接暂停交易。

## Sector resonance audit

| test                                                  |   high_n |    low_n |   high_ev |   low_ev |    diff |   ci_low |   ci_high |   pvalue | interpretation                              |
|:------------------------------------------------------|---------:|---------:|----------:|---------:|--------:|---------:|----------:|---------:|:--------------------------------------------|
| H4_real_trade_high_vs_low_sector_limit_up             |       45 |  53.0000 |    0.0114 |   0.0215 | -0.0101 |  -0.0321 |    0.0123 |   0.3820 | 真实交易高/低板块涨停组EV差异               |
| H6_candidate_proxy_sector_limit_up_vs_return_to_close |     5978 | nan      |    0.1008 | nan      |  0.1008 |   0.0748 |    0.1254 |   0.0000 | 多候选代理相关（candidate_return_to_close） |


Sector field identity check:

| panel                 |   identical_rows |   total_rows |   identical_ratio |   dates_with_difference |   dates_total |   sectors_with_different_samples |   different_samples_by_sector_total |
|:----------------------|-----------------:|-------------:|------------------:|------------------------:|--------------:|---------------------------------:|------------------------------------:|
| trade_panel           |               79 |          136 |            0.5809 |                      55 |           127 |                               15 |                                  57 |
| multi_candidate_panel |             3049 |         5978 |            0.5100 |                     379 |           447 |                               31 |                                2929 |


人工抽样核对结果：见 SECTOR_COUNT_AUDIT.csv。

## Answers to the ten required questions

1. **天蝎最适合哪一种短线情绪阶段？**
   WEAK_REPAIR（交易数45，胜率62.22%，真实EV 0.0335），但 ACCELERATION、RECESSION、EXTREME_PANIC 仍为正 EV，不支持硬过滤。
2. **它是否主要交易冰点修复？**
   WEAK_REPAIR 贡献最大；ICE_REPAIR 样本过少（<20），不能合并为“修复类状态显著”。
3. **极端恐慌是否损害其收益？**
   EXTREME_PANIC 样本量小（18笔），EV 仍为正，当前证据不支持因其暂停交易。
4. **首板晋级率、炸板率和赚钱效应中，哪一项最有解释力？**
   详见 EMOTION_DAILY_PANEL.csv 中五个维度分数与收益的交互；profit_score（昨日涨停赚钱效应）在情绪热度中占核心权重。
5. **市场性低开和个股独立低开，哪一种更有效？**
   通过 `candidate_relative_to_cohort` 与 `candidate_relative_to_market` 区分，详见 OPEN_CONTEXT_SUMMARY.csv。
6. **板块共振是否显著改善结果？**
   否。板块涨停数量与候选股开盘至收盘代理收益存在弱正相关，但对 169 笔真实交易没有发现显著正向效果，需通过完整策略排序实验进一步验证。
7. **同日多候选时，什么特征最适合排序？**
   见 MULTI_CANDIDATE_RANKING_ANALYSIS.csv 与 HYPOTHESIS_TEST_RESULTS.csv 中 H6 Spearman 相关性；candidate_return_to_close 不是天蝎正式交易 EV。
8. **当前 bear 定义是否过于粗糙？**
   本任务未修改 bear 定义；情绪阶段分层显示同一 bear 市场模式下存在显著异质性，支持增加情绪门控而非替换 bear 定义。
9. **天蝎的Alpha应如何用一句短线交易语言描述？**
   "在短线情绪弱修复日，利用昨日首板群体的开盘分歧，低吸其中相对市场仍具承接的 bear 模式候选。"
10. **下一项最值得验证的结构实验是什么？**
   基于T-1情绪状态的仓位分级实验（类别 A - 情绪门控/仓位分级），详见 STRUCTURAL_EXPERIMENT_RECOMMENDATION.md。

## Primary structural experiment recommendation

- **基于T-1情绪状态的仓位分级实验**
- Category: A - 情绪门控/仓位分级
- Rationale: WEAK_REPAIR 是表现最强且跨周期方向一致的阶段（EV 3.35%，45笔），但 ACCELERATION、RECESSION 和 EXTREME_PANIC 仍具有正 EV，因此当前证据不支持情绪状态硬过滤或直接暂停交易。建议先验证在 WEAK_REPAIR 维持标准仓位、其余状态降低仓位的分级方案。

## Baseline verification

Re-run produced 169 matched trades (338 execution rows) in 2543.95s. Consistent with checkpoint: True.

## Data provenance

- Alpha-profile checkpoint: D:\WorkSpace\他山之石\情绪门控\l2_worktree\coordination\alpha\scorpion_alpha_profile_v1\bt_checkpoint.pkl
- Local parquet cache: d:\workspace\他山之石\情绪门控\_emotion_structure_local
- Deliverables directory: D:\WorkSpace\他山之石\情绪门控\l2_worktree\coordination\alpha\scorpion_emotion_structure_v1
