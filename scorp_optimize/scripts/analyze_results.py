import os
import re
import pandas as pd
import numpy as np

ROOT = r"D:\Work Space\他山之石\情绪门控"
RUNS_DIR = os.path.join(ROOT, "scorp_optimize", "runs")
YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
INIT_CASH = 1_000_000.0

STRATEGIES = ["baseline", "v227_yjj", "v227_scorp", "rzq", "rzq_original", "zb", "auction"]

# Map branch codes to human-readable names
BRANCH_NAMES = {
    "v227_yjj": "v227一进二",
    "v227_scorp": "v227天蝎座",
    "rzq": "rzq",
    "rzq_original": "rzq_original",
    "zb": "zb",
    "auction": "竞价袖套"
}

def load_trading_dates():
    idx_path = os.path.join(ROOT, "idx_000852.parquet")
    if os.path.exists(idx_path):
        df = pd.read_parquet(idx_path)
        dates_dt = pd.to_datetime(df['date'])
        dates = sorted(dates_dt.dt.strftime('%Y-%m-%d').tolist())
        return dates
    return []

TRADE_DATES = load_trading_dates()
TRADE_DATES_SET = set(TRADE_DATES)

def get_holding_days(entry_date, exit_date):
    e_str = str(entry_date).split(' ')[0]
    x_str = str(exit_date).split(' ')[0]
    if e_str in TRADE_DATES_SET and x_str in TRADE_DATES_SET:
        return TRADE_DATES.index(x_str) - TRADE_DATES.index(e_str)
    try:
        return (pd.to_datetime(x_str) - pd.to_datetime(e_str)).days
    except:
        return 0

def parse_market_modes():
    daily_modes = {}
    log_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) [^\]]+\] INFO: 模式=(bear|cautious|bull)")
    
    baseline_dir = os.path.join(RUNS_DIR, "baseline")
    if not os.path.exists(baseline_dir):
        return {}
        
    for year in YEARS:
        log_path = os.path.join(baseline_dir, f"{year}_run.log")
        if not os.path.exists(log_path):
            continue
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = log_re.match(line)
                if m:
                    date_str, mode = m.groups()
                    daily_modes[date_str] = mode
    return daily_modes

def parse_baseline_buy_branches():
    # Map (date, code) -> branch for baseline purchases
    buy_branches = {}
    buy_log_re = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}) [^\]]+\] INFO: \[(v227买|天蝎座|rzq买|zb买|竞价买)\]\s*(\d{6}\.XSH[GE])"
    )
    
    baseline_dir = os.path.join(RUNS_DIR, "baseline")
    if not os.path.exists(baseline_dir):
        return {}
        
    branch_map = {
        "v227买": "v227_yjj",
        "天蝎座": "v227_scorp",
        "rzq买": "rzq",
        "zb买": "zb",
        "竞价买": "auction"
    }
    
    for year in YEARS:
        log_path = os.path.join(baseline_dir, f"{year}_run.log")
        if not os.path.exists(log_path):
            continue
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = buy_log_re.match(line)
                if m:
                    date_str, label, code = m.groups()
                    buy_branches[(date_str, code)] = branch_map[label]
    return buy_branches

def match_trades(trades_df):
    if trades_df.empty:
        return pd.DataFrame()
        
    trades = trades_df.copy()
    trades['date'] = trades['time'].apply(lambda x: str(x).split(' ')[0])
    trades['price'] = pd.to_numeric(trades['price'])
    trades['amount'] = pd.to_numeric(trades['amount'])
    
    # Sort by execution order
    trades['num_id'] = trades['trade_id'].str.replace('t_', '').astype(int)
    trades = trades.sort_values('num_id')
    
    matched = []
    open_positions = {} # code -> list of dicts: {'date', 'price', 'amount', 'commission', 'tax'}
    
    for _, row in trades.iterrows():
        code = row['code']
        amount = row['amount']
        price = row['price']
        date = row['date']
        comm = row['commission']
        tax = row['tax']
        
        if amount > 0:
            if code not in open_positions:
                open_positions[code] = []
            open_positions[code].append({
                'date': date,
                'price': price,
                'amount': amount,
                'comm': comm,
                'tax': tax
            })
        elif amount < 0:
            sell_amount_abs = abs(amount)
            if code not in open_positions or not open_positions[code]:
                continue
                
            # Match FIFO
            matched_lots = []
            rem_sell = sell_amount_abs
            while rem_sell > 0 and open_positions[code]:
                lot = open_positions[code][0]
                lot_amount = lot['amount']
                if lot_amount <= rem_sell:
                    matched_lots.append(lot)
                    rem_sell -= lot_amount
                    open_positions[code].pop(0)
                else:
                    matched_lots.append({
                        'date': lot['date'],
                        'price': lot['price'],
                        'amount': rem_sell,
                        'comm': lot['comm'] * (rem_sell / lot_amount),
                        'tax': lot['tax'] * (rem_sell / lot_amount)
                    })
                    lot['amount'] -= rem_sell
                    lot['comm'] -= lot['comm'] * (rem_sell / lot_amount)
                    lot['tax'] -= lot['tax'] * (rem_sell / lot_amount)
                    rem_sell = 0
            
            if matched_lots:
                total_shares = sum(l['amount'] for l in matched_lots)
                weighted_buy_price = sum(l['price'] * l['amount'] for l in matched_lots) / total_shares
                buy_date = matched_lots[0]['date']
                
                ret = (price - weighted_buy_price) / weighted_buy_price
                
                # Determine exit reason (from EOD, every_bar, morning, midday, etc.)
                time_str = str(row['time'])
                exit_reason = "unknown"
                if "every_bar" in time_str:
                    exit_reason = "stop_loss"
                elif "11:25" in time_str or "11:28" in time_str or "11:30" in time_str:
                    exit_reason = "profit_sell"
                elif "13:01" in time_str:
                    exit_reason = "midday_loss_sell"
                elif "14:50" in time_str or "14:47" in time_str or "14:48" in time_str:
                    exit_reason = "eod_clear"
                
                matched.append({
                    'code': code,
                    'entry_date': buy_date,
                    'exit_date': date,
                    'buy_price': weighted_buy_price,
                    'sell_price': price,
                    'shares': total_shares,
                    'ret': ret,
                    'exit_reason': exit_reason,
                    'year': row['year']
                })
                
    return pd.DataFrame(matched)

def calculate_metrics_from_matched(matched_df, equity_df, year_label):
    if equity_df.empty:
        return {}
        
    final_val = equity_df['value'].iloc[-1]
    initial_val = equity_df['value'].iloc[0]
    tot_ret = final_val / initial_val - 1
    
    peak = equity_df['value'].cummax()
    dd = equity_df['value'] / peak - 1
    max_dd = dd.min()
    
    num_trades = len(matched_df)
    
    if num_trades > 0:
        ret = matched_df['ret']
        win_rate = (ret > 0).mean()
        avg_ret = ret.mean()
        
        gains = ret[ret > 0]
        losses = ret[ret <= 0]
        avg_gain = gains.mean() if len(gains) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
        p_l_ratio = avg_gain / avg_loss if avg_loss > 0 else np.nan
        
        matched_df = matched_df.copy()
        matched_df['holding_days'] = matched_df.apply(lambda r: get_holding_days(r['entry_date'], r['exit_date']), axis=1)
        avg_holding = matched_df['holding_days'].mean()
    else:
        win_rate = np.nan
        avg_ret = np.nan
        p_l_ratio = np.nan
        avg_holding = np.nan
        
    return {
        "year": year_label,
        "return": tot_ret,
        "max_dd": max_dd,
        "trades": num_trades,
        "win_rate": win_rate,
        "avg_ret": avg_ret,
        "p_l_ratio": p_l_ratio,
        "avg_holding": avg_holding,
        "final_val": final_val
    }

def main():
    daily_modes = parse_market_modes()
    buy_branches = parse_baseline_buy_branches()
    print(f"Loaded {len(daily_modes)} days of market mode annotations.", flush=True)
    print(f"Loaded {len(buy_branches)} baseline buy labels.", flush=True)

    all_matched = {}
    all_equity = {}

    # Load and process backtest runs for each strategy
    for name in STRATEGIES:
        all_equity[name] = []
        year_trades = []
        strategy_dir = os.path.join(RUNS_DIR, name)
        
        for year in YEARS:
            eq_path = os.path.join(strategy_dir, f"{year}_equity.csv")
            tr_path = os.path.join(strategy_dir, f"{year}_trades.csv")
            if os.path.exists(eq_path) and os.path.exists(tr_path):
                eq = pd.read_csv(eq_path)
                tr = pd.read_csv(tr_path)
                eq['year'] = year
                tr['year'] = year
                all_equity[name].append(eq)
                year_trades.append(tr)
                
        if all_equity[name]:
            combined_tr = pd.concat(year_trades, ignore_index=True)
            # Reconstruct matched round-trip trades
            all_matched[name] = match_trades(combined_tr)
        else:
            all_matched[name] = pd.DataFrame()

    # 1. Baseline Trade Classification
    if "baseline" in all_matched and not all_matched["baseline"].empty:
        base_matched = all_matched["baseline"]
        # Map branch using the log parsed map
        def get_branch(r):
            key = (r['entry_date'], r['code'])
            return buy_branches.get(key, "unknown")
            
        base_matched['branch'] = base_matched.apply(get_branch, axis=1)
    
    # 2. Performance Summary Table
    annual_rows = []
    for name in STRATEGIES:
        if name not in all_equity or not all_equity[name]:
            continue
        
        # Build compounded continuous equity curve
        compounded_dfs = []
        current_multiplier = 1.0
        for eq_year_df in all_equity[name]:
            norm_val = eq_year_df['value'] / eq_year_df['value'].iloc[0]
            comp_val = norm_val * (current_multiplier * INIT_CASH)
            
            year_copy = eq_year_df.copy()
            year_copy['value'] = comp_val
            compounded_dfs.append(year_copy)
            
            current_multiplier = comp_val.iloc[-1] / INIT_CASH
            
        compounded_eq = pd.concat(compounded_dfs, ignore_index=True)
        matched_df = all_matched[name]
        
        # Yearly (calculated on original uncompounded yearly df for year-by-year independence)
        for year_df in all_equity[name]:
            year = year_df['year'].iloc[0]
            y_matched = matched_df[matched_df['year'] == year]
            metrics = calculate_metrics_from_matched(y_matched, year_df, year)
            metrics['strategy'] = name
            annual_rows.append(metrics)
                
        # Total overall (calculated on compounded continuous curve)
        total_metrics = calculate_metrics_from_matched(matched_df, compounded_eq, "Total")
        total_metrics['strategy'] = name
        annual_rows.append(total_metrics)
        
    df_annual = pd.DataFrame(annual_rows)

    # 3. Performance by Market State
    state_rows = []
    for name in STRATEGIES:
        matched_df = all_matched[name]
        if matched_df.empty:
            continue
        matched_df = matched_df.copy()
        matched_df['mode'] = matched_df['entry_date'].map(daily_modes).fillna('unknown')
        
        for mode in ['bull', 'cautious', 'bear']:
            mode_trades = matched_df[matched_df['mode'] == mode]
            num_trades = len(mode_trades)
            if num_trades > 0:
                win_rate = (mode_trades['ret'] > 0).mean()
                avg_ret = mode_trades['ret'].mean()
                holding = mode_trades.apply(lambda r: get_holding_days(r['entry_date'], r['exit_date']), axis=1).mean()
            else:
                win_rate = np.nan
                avg_ret = np.nan
                holding = np.nan
            state_rows.append({
                "strategy": name,
                "mode": mode,
                "trades": num_trades,
                "win_rate": win_rate,
                "avg_ret": avg_ret,
                "holding_days": holding
            })
    df_state = pd.DataFrame(state_rows)

    # 4. Exit reasons
    exit_rows = []
    for name in STRATEGIES:
        matched_df = all_matched[name]
        if matched_df.empty:
            continue
        counts = matched_df['exit_reason'].value_counts()
        for reason, cnt in counts.items():
            exit_rows.append({
                "strategy": name,
                "reason": reason,
                "count": cnt,
                "pct": cnt / len(matched_df)
            })
    df_exit = pd.DataFrame(exit_rows)

    # 5. Gatekeeper Contribution Analysis
    # We compare the trades in each Bare strategy against Gated branch trades in Baseline.
    # Baseline gated branch trades are filtered from base_matched by 'branch'.
    gate_rows = []
    
    # We loop over the 5 bare branches
    for branch_code in ["v227_yjj", "v227_scorp", "rzq", "zb", "auction"]:
        bare_name = branch_code
        bare_trades = all_matched.get(bare_name, pd.DataFrame())
        
        # Gated trades in baseline
        if "baseline" in all_matched and not all_matched["baseline"].empty:
            gated_trades = all_matched["baseline"][all_matched["baseline"]['branch'] == branch_code]
        else:
            gated_trades = pd.DataFrame()
            
        if bare_trades.empty:
            continue
            
        # Match bare trades to gated trades to find:
        # - Traded (in Gated): trades present in both.
        # - Filtered out (in Bare but NOT in Gated): trades blocked by gatekeepers.
        # We match based on (entry_date, code).
        gated_keys = set(zip(gated_trades['entry_date'], gated_trades['code']))
        
        # Segment bare trades
        filtered_trades = bare_trades[~bare_trades.apply(lambda r: (r['entry_date'], r['code']) in gated_keys, axis=1)]
        kept_trades = bare_trades[bare_trades.apply(lambda r: (r['entry_date'], r['code']) in gated_keys, axis=1)]
        
        # Compute metrics for each segment
        def get_summary(df, label):
            num = len(df)
            if num > 0:
                win_rate = (df['ret'] > 0).mean()
                avg_ret = df['ret'].mean()
                total_pnl = df['ret'].sum() # cumulative arithmetic return sum for proxy
            else:
                win_rate = np.nan
                avg_ret = np.nan
                total_pnl = 0.0
            return {
                "trades": num,
                "win_rate": win_rate,
                "avg_ret": avg_ret,
                "total_pnl": total_pnl
            }
            
        bare_sum = get_summary(bare_trades, "Bare")
        kept_sum = get_summary(kept_trades, "Kept")
        filtered_sum = get_summary(filtered_trades, "Filtered")
        
        # Log analysis
        # If filtered trades have negative return, gate was helpful.
        # If filtered trades have positive return, gate was harmful (cut alpha).
        gate_utility = "有益" if filtered_sum['avg_ret'] < 0 else "有害" if filtered_sum['avg_ret'] > 0 else "中性"
        
        gate_rows.append({
            "branch": BRANCH_NAMES[branch_code],
            "bare_trades": bare_sum['trades'],
            "bare_ret": bare_sum['avg_ret'],
            "kept_trades": kept_sum['trades'],
            "kept_ret": kept_sum['avg_ret'],
            "filtered_trades": filtered_sum['trades'],
            "filtered_ret": filtered_sum['avg_ret'],
            "filtered_win": filtered_sum['win_rate'],
            "utility": gate_utility
        })
    df_gate = pd.DataFrame(gate_rows)

    # 6. Save results to CSVs
    out_dir = os.path.join(ROOT, "bare_runs_analysis", "results")
    os.makedirs(out_dir, exist_ok=True)
    df_annual.to_csv(os.path.join(out_dir, "annual_summary.csv"), index=False)
    df_state.to_csv(os.path.join(out_dir, "state_summary.csv"), index=False)
    df_exit.to_csv(os.path.join(out_dir, "exit_summary.csv"), index=False)
    df_gate.to_csv(os.path.join(out_dir, "gate_analysis.csv"), index=False)
    
    # 7. Generate markdown report
    generate_markdown_report(df_annual, df_state, df_exit, df_gate)

def pct(x):
    if pd.isna(x):
        return "-"
    return f"{x:.2%}"

def num(x):
    if pd.isna(x):
        return "-"
    return f"{x:.2f}"

def generate_markdown_report(df_annual, df_state, df_exit, df_gate):
    md = []
    md.append("# 情绪门控策略各分支裸跑能力评估报告")
    md.append("")
    md.append("本报告评估了在**不考虑任何外部市场状态机、情绪门控、冷却机制、仓位控制、策略路由**的情况下，母版五个交易分支（`v227一进二`、`v227天蝎座`、`rzq`、`zb`、`竞价袖套`）单独生存的独立盈利能力，并与原始混跑基线策略（`baseline`）进行详细对比。")
    md.append("")
    
    md.append("## 一、 分年度裸跑表现概览")
    md.append("下表展示了基线混跑策略与5个裸跑分支在 2020 - 2026 年（截至2026-06-06）的分年度回测业绩（年化收益率以期末净值/期初净值-1表示，最大回撤为全期最大回撤）：")
    md.append("")
    
    # Format annual summary table
    annual_view = df_annual.copy()
    annual_view['return'] = annual_view['return'].map(pct)
    annual_view['max_dd'] = annual_view['max_dd'].map(pct)
    annual_view['win_rate'] = annual_view['win_rate'].map(pct)
    annual_view['avg_ret'] = annual_view['avg_ret'].map(pct)
    annual_view['p_l_ratio'] = annual_view['p_l_ratio'].map(num)
    annual_view['avg_holding'] = annual_view['avg_holding'].map(num)
    
    for name in STRATEGIES:
        strategy_display = f"### 策略: {name}"
        if name == "baseline":
            strategy_display = "### 基线策略 (Baseline - 情绪门控完整版)"
        elif name == "v227_yjj":
            strategy_display = "### 裸跑分支: v227一进二 (YJJ)"
        elif name == "v227_scorp":
            strategy_display = "### 裸跑分支: v227天蝎座 (Scorpion)"
        elif name == "rzq":
            strategy_display = "### 裸跑分支: rzq"
        elif name == "zb":
            strategy_display = "### 裸跑分支: zb"
        elif name == "auction":
            strategy_display = "### 裸跑分支: 竞价袖套 (Auction)"
            
        md.append(strategy_display)
        sub_df = annual_view[annual_view['strategy'] == name].drop(columns=['strategy'])
        md.append(sub_df.to_markdown(index=False))
        md.append("")
        
    md.append("## 二、 不同市场状态下的业绩特征")
    md.append("下表展示了各策略在基线识别的 `bull`（牛市）、`cautious`（震荡/谨慎）、`bear`（熊市）三种市场状态下的单笔平均收益率和胜率：")
    md.append("")
    
    state_view = df_state.copy()
    state_view['win_rate'] = state_view['win_rate'].map(pct)
    state_view['avg_ret'] = state_view['avg_ret'].map(pct)
    state_view['holding_days'] = state_view['holding_days'].map(num)
    md.append(state_view.to_markdown(index=False))
    md.append("")
    
    md.append("## 三、 门控（Gatekeeper）贡献分析")
    md.append("通过比较裸跑分支与基线策略在同一时间发生的交易，我们可以识别出**被情绪门控/冷却机制过滤掉的交易**（即“裸跑有交易，但基线未入场”）。统计这些被过滤掉的交易的平均收益，可以量化评估门控机制的真实贡献：")
    md.append("")
    
    gate_view = df_gate.copy()
    gate_view['bare_ret'] = gate_view['bare_ret'].map(pct)
    gate_view['kept_ret'] = gate_view['kept_ret'].map(pct)
    gate_view['filtered_ret'] = gate_view['filtered_ret'].map(pct)
    gate_view['filtered_win'] = gate_view['filtered_win'].map(pct)
    md.append(gate_view.to_markdown(index=False))
    md.append("")
    md.append("> **分析说明**：")
    md.append("> - **过滤交易收益为负（有益）**：表示门控机制成功帮策略规避了亏损交易，对最终净值有正面保护作用。")
    md.append("> - **过滤交易收益为正（有害）**：表示门控机制产生了误伤，错误过滤掉了原本能赚钱的盈利交易，降低了策略的整体收益。")
    md.append("")
    
    md.append("## 四、 卖出原因分布")
    md.append("下表统计了每个裸跑策略的各种卖出平仓原因（止盈、移动止损、午间止损、尾盘清仓等）占比，用于诊断策略的退出效率：")
    md.append("")
    
    exit_view = df_exit.copy()
    exit_view['pct'] = exit_view['pct'].map(pct)
    md.append(exit_view.to_markdown(index=False))
    md.append("")
    
    report_path = os.path.join(ROOT, "bare_runs_analysis", "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Generated analytical report at {report_path}", flush=True)

    # Automatically copy to walkthrough.md in the artifacts folder
    artifacts_dir = r"C:\Users\Zhu Yu\.gemini\antigravity\brain\f0bae430-075c-424c-9def-19ac537628ae"
    if os.path.exists(artifacts_dir):
        walkthrough_path = os.path.join(artifacts_dir, "walkthrough.md")
        with open(walkthrough_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        print(f"Generated walkthrough artifact at {walkthrough_path}", flush=True)

if __name__ == "__main__":
    main()
