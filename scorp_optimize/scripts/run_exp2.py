import os
import sys
import time
import importlib
import traceback
import gc
import pandas as pd
import numpy as np

ROOT = r"D:\Work Space\他山之石\情绪门控"
WORK = os.path.join(ROOT, "rebuild_from_archive")

sys.path.insert(0, WORK)
sys.path.insert(1, ROOT)
sys.path.insert(2, r"D:\work space\hdata")
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from scripts.core import hdata_reader
from engine.core import Engine

# 实验二：候选股 Slots 数量扩容测试
# Slots = 1, 3, 5 (基线为 2，即当前主策略)
EXP_CONFIGS = {
    "v227_scorp_exp2_s1": (1, "g.v227_slots, g.rzq_slots, g.zb_slots = 1, 0, 0"),
    "v227_scorp_exp2_s3": (3, "g.v227_slots, g.rzq_slots, g.zb_slots = 3, 0, 0"),
    "v227_scorp_exp2_s5": (5, "g.v227_slots, g.rzq_slots, g.zb_slots = 5, 0, 0"),
}

YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

def generate_exp_strategies():
    scorp_path = os.path.join(ROOT, "bare_runs_analysis", "strategies", "strategy_v227_scorp.py")
    with open(scorp_path, "r", encoding="utf-8") as f:
        code = f.read()

    # 替换目标文本：
    target_str = "g.v227_slots, g.rzq_slots, g.zb_slots = 2, 0, 0"
    if target_str not in code:
        print("[ERROR] Could not find slots initialization string in strategy_v227_scorp.py!")
        sys.exit(1)

    generated_paths = {}
    for name, (slots, replacement) in EXP_CONFIGS.items():
        exp_code = code.replace(target_str, replacement)
        path = os.path.join(ROOT, "bare_runs_analysis", "strategies", f"{name}.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(exp_code)
        print(f"Generated strategy file for Slots={slots}: {path}")
        generated_paths[name] = path

    return generated_paths

def run_backtests(strategies):
    out_base = os.path.join(ROOT, "bare_runs_analysis", "runs")
    
    for name, path in strategies.items():
        print(f"\n=================== Strategy: {name} ===================", flush=True)
        strategy_dir = os.path.join(out_base, name)
        os.makedirs(strategy_dir, exist_ok=True)
        
        with open(path, "r", encoding="utf-8") as f:
            strategy_code = f.read()
            
        for year in YEARS:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31" if year < 2026 else "2026-06-06"
            
            equity_path = os.path.join(strategy_dir, f"{year}_equity.csv")
            trades_path = os.path.join(strategy_dir, f"{year}_trades.csv")
            log_path = os.path.join(strategy_dir, f"{year}_run.log")
            
            if os.path.exists(equity_path) and os.path.exists(trades_path) and os.path.exists(log_path):
                if os.path.getsize(equity_path) > 0 and os.path.getsize(trades_path) > 0:
                    print(f"[{name} - {year}] Already completed, skipping.", flush=True)
                    continue
            
            hdata_reader.clear_cache()
            gc.collect()
            
            print(f"[{name} - {year}] Running {year} ({start_date} to {end_date})...", flush=True)
            preload_years = {year - 2, year - 1, year}
            hdata_reader._update_pivot_cache(preload_years)
            
            start = time.time()
            try:
                engine = Engine(strategy_code, start_date, end_date, 1000000)
                equity, trades, logs, metrics = engine.run()
                elapsed = time.time() - start
                
                equity.to_csv(equity_path, index=False)
                trades.to_csv(trades_path, index=False)
                with open(log_path, "w", encoding="utf-8") as lf:
                    for line in logs:
                        lf.write(line + "\n")
                
                print(f"[{name} - {year}] Completed in {elapsed:.2f}s | Trades: {len(trades)} | End Val: {equity['value'].iloc[-1]:.1f}", flush=True)
            except Exception as e:
                print(f"[{name} - {year}] Failed!", flush=True)
                traceback.print_exc()

def load_trading_dates():
    idx_path = os.path.join(ROOT, "idx_000852.parquet")
    if os.path.exists(idx_path):
        df = pd.read_parquet(idx_path)
        dates_dt = pd.to_datetime(df['date'])
        return sorted(dates_dt.dt.strftime('%Y-%m-%d').tolist())
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

def match_trades(trades_df):
    if trades_df.empty:
        return pd.DataFrame()
        
    trades = trades_df.copy()
    trades['date'] = trades['time'].apply(lambda x: str(x).split(' ')[0])
    trades['price'] = pd.to_numeric(trades['price'])
    trades['amount'] = pd.to_numeric(trades['amount'])
    trades['num_id'] = trades['trade_id'].str.replace('t_', '').astype(int)
    trades = trades.sort_values('num_id')
    
    matched = []
    open_positions = {}
    
    for _, row in trades.iterrows():
        code = row['code']
        amount = row['amount']
        price = row['price']
        date = row['date']
        
        if amount > 0:
            if code not in open_positions:
                open_positions[code] = []
            open_positions[code].append({'date': date, 'price': price, 'amount': amount})
        elif amount < 0:
            sell_amount_abs = abs(amount)
            if code not in open_positions or not open_positions[code]:
                continue
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
                    matched_lots.append({'date': lot['date'], 'price': lot['price'], 'amount': rem_sell})
                    lot['amount'] -= rem_sell
                    rem_sell = 0
            
            if matched_lots:
                total_shares = sum(l['amount'] for l in matched_lots)
                weighted_buy_price = sum(l['price'] * l['amount'] for l in matched_lots) / total_shares
                buy_date = matched_lots[0]['date']
                ret = (price - weighted_buy_price) / weighted_buy_price
                matched.append({
                    'code': code,
                    'entry_date': buy_date,
                    'exit_date': date,
                    'buy_price': weighted_buy_price,
                    'sell_price': price,
                    'shares': total_shares,
                    'ret': ret,
                    'year': row['year']
                })
    return pd.DataFrame(matched)

def analyze_results_metrics():
    print("\n=================== Experiment 2 Analysis ===================", flush=True)
    out_base = os.path.join(ROOT, "bare_runs_analysis", "runs")
    
    # 包含 baseline (Slots=2) 和其它 Slots 测试策略
    strategies_to_analyze = {
        "v227_scorp_exp2_s1": "Slots = 1",
        "v227_scorp": "Slots = 2 (Baseline)",
        "v227_scorp_exp2_s3": "Slots = 3",
        "v227_scorp_exp2_s5": "Slots = 5",
    }
    
    results = []
    for name, label in strategies_to_analyze.items():
        strategy_dir = os.path.join(out_base, name)
        
        all_equity_dfs = []
        all_trades_dfs = []
        
        for year in YEARS:
            eq_path = os.path.join(strategy_dir, f"{year}_equity.csv")
            tr_path = os.path.join(strategy_dir, f"{year}_trades.csv")
            if os.path.exists(eq_path) and os.path.exists(tr_path):
                eq = pd.read_csv(eq_path)
                try:
                    tr = pd.read_csv(tr_path)
                except pd.errors.EmptyDataError:
                    tr = pd.DataFrame(columns=['time', 'code', 'amount', 'price', 'commission', 'tax', 'trade_id', 'order_id', 'year'])
                eq['year'] = year
                tr['year'] = year
                all_equity_dfs.append(eq)
                all_trades_dfs.append(tr)
        
        if not all_equity_dfs:
            print(f"[{name}] No backtest outputs found.")
            continue
            
        compounded_dfs = []
        current_multiplier = 1.0
        for eq_year_df in all_equity_dfs:
            norm_val = eq_year_df['value'] / eq_year_df['value'].iloc[0]
            comp_val = norm_val * (current_multiplier * 1000000.0)
            year_copy = eq_year_df.copy()
            year_copy['value'] = comp_val
            compounded_dfs.append(year_copy)
            current_multiplier = comp_val.iloc[-1] / 1000000.0
            
        compounded_eq = pd.concat(compounded_dfs, ignore_index=True)
        combined_tr = pd.concat(all_trades_dfs, ignore_index=True)
        matched_tr = match_trades(combined_tr)
        
        final_val = compounded_eq['value'].iloc[-1]
        tot_ret = final_val / 1000000.0 - 1
        peak = compounded_eq['value'].cummax()
        dd = compounded_eq['value'] / peak - 1
        max_dd = dd.min()
        
        num_trades = len(matched_tr)
        if num_trades > 0:
            win_rate = (matched_tr['ret'] > 0).mean()
            avg_ret = matched_tr['ret'].mean()
            matched_tr['holding_days'] = matched_tr.apply(lambda r: get_holding_days(r['entry_date'], r['exit_date']), axis=1)
            avg_holding = matched_tr['holding_days'].mean()
            
            gains = matched_tr[matched_tr['ret'] > 0]['ret']
            losses = matched_tr[matched_tr['ret'] <= 0]['ret']
            avg_gain = gains.mean() if len(gains) > 0 else 0
            avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
            p_l_ratio = avg_gain / avg_loss if avg_loss > 0 else np.nan
        else:
            win_rate = np.nan
            avg_ret = np.nan
            avg_holding = np.nan
            p_l_ratio = np.nan
            
        results.append({
            "仓位限制": label,
            "总收益率": f"{tot_ret:.2%}",
            "最大回撤": f"{max_dd:.2%}",
            "交易笔数": num_trades,
            "胜率": f"{win_rate:.2%}" if not pd.isna(win_rate) else "-",
            "单笔EV": f"{avg_ret:.2%}" if not pd.isna(avg_ret) else "-",
            "单笔盈亏比": f"{p_l_ratio:.2f}" if not pd.isna(p_l_ratio) else "-",
            "平均持股天数": f"{avg_holding:.1f}" if not pd.isna(avg_holding) else "-",
        })
        
    df_res = pd.DataFrame(results)
    print("\n" + df_res.to_markdown(index=False) + "\n")
    
    report_path = os.path.join(ROOT, "bare_runs_analysis", "exp2_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 实验二：候选股 Slots 上限评估报告\n\n")
        f.write(df_res.to_markdown(index=False) + "\n")
    print(f"Generated Experiment 2 report at {report_path}")

def main():
    generated = generate_exp_strategies()
    run_backtests(generated)
    analyze_results_metrics()

if __name__ == "__main__":
    main()
