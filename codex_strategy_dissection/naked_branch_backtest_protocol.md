# 裸分支回放协议

目标：

在优化混合母版之前，先看每个分支在“没有跨分支路由竞争”时的单独质量。

这和 `branch_state_attribution.csv` 不同：

- `branch_state_attribution.csv` 只描述母版实际成交的交易。
- 裸分支回放允许某个分支在母版原本会挡掉它的日子出手。

## 策略副本

源策略：

- `../母版-20260506-Clone-分支净化回测.py`

不直接修改源策略。使用：

- `make_branch_strategy_copies.py`

在本目录生成独立副本：

- `branch_strategies/mother_branch_force_v227.py`
- `branch_strategies/mother_branch_force_rzq.py`
- `branch_strategies/mother_branch_force_zb.py`
- `branch_strategies/mother_branch_force_rzq_zb.py`
- `branch_strategies/mother_branch_force_auction.py`

每个副本文件里都写死对应的 `g.branch_test = 'force_*'`，可以人工打开确认。

## 模式

强制分支模式：

- `force_v227`：只开 V227 路线。它内部仍包含 bull/cautious 的 YJJ 和 bear 的 scorpion。
- `force_rzq`：只开 RZQ。
- `force_zb`：只开 ZB。
- `force_rzq_zb`：RZQ 和 ZB 一起开，但不和 V227 竞争 active。
- `force_auction`：只开竞价袖套。

对照模式：

- `normal`：母版原路由。
- `mix_*`：保留母版路由，只在母版允许该分支时交易。它不是裸分支，只能做对照。

## 保留什么

当前裸回放是“单分支策略质量”，不是纯信号 markout。它仍然保留：

- 候选生成规则
- 分支内部买入过滤
- 分支卖出规则
- T+1 和本地引擎成交规则
- 分支止损和跟踪止盈

## 关闭什么

强制模式关闭的是跨分支路由竞争：

- 不让 active 路由挡住被测试分支。
- 不让其他核心分支抢仓位，除非模式本身包含多个分支。
- 竞价只在 `force_auction` 中开启。

## 下一层更纯的信号测试

如果要看更纯的“裸信号”，还需要额外版本：

- 去掉各买入函数内部的 `market_mode` 判断。
- 去掉 `fb_pct` 毒区判断。
- 去掉分支内部冷却。
- 统一 slot 和目标仓位。

这应当作为第二层实验，因为它已经从“单分支策略”变成“原始信号打点”。

## 输出

runner 只写：

- `codex_strategy_dissection/branch_runs/`

每次回放输出：

- `local_equity_<mode>_<start>_<end>.csv`
- `local_trades_<mode>_<start>_<end>.csv`
- `local_run_<mode>_<start>_<end>.log`
- `naked_branch_summary.csv`
