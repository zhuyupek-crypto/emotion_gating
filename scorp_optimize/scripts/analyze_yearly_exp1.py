import os
import sys
import pandas as pd
import numpy as np

ROOT = r"D:\Work Space\他山之石\情绪门控"
RUNS_DIR = os.path.join(ROOT, "bare_runs_analysis", "runs")
YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

STRATEGIES = {
    "v227_scorp_exp1_A": "-2% ~ -3%",
    "v227_scorp": "-3% ~ -4% (Baseline)",
    "v227_scorp_exp1_C": "-4% ~ -5%",
    "v227_scorp_exp1_D": "-5% ~ -6%",
}

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

def main():
    rows = []
    for name, label in STRATEGIES.items():
        strategy_dir = os.path.join(RUNS_DIR, name)
        
        for year in YEARS:
            eq_path = os.path.join(strategy_dir, f"{year}_equity.csv")
            tr_path = os.path.join(strategy_dir, f"{year}_trades.csv")
            
            if os.path.exists(eq_path) and os.path.exists(tr_path):
                try:
                    eq = pd.read_csv(eq_path)
                    try:
                        tr = pd.read_csv(tr_path)
                    except pd.errors.EmptyDataError:
                        tr = pd.DataFrame(columns=['time', 'code', 'amount', 'price', 'commission', 'tax', 'trade_id', 'order_id'])
                    tr['year'] = year
                    matched = match_trades(tr)
                    
                    year_ret = eq['value'].iloc[-1] / eq['value'].iloc[0] - 1
                    trades_cnt = len(matched)
                    
                    if trades_cnt > 0:
                        win_rate = (matched['ret'] > 0).mean()
                        ev = matched['ret'].mean()
                    else:
                        win_rate = np.nan
                        ev = np.nan
                        
                    rows.append({
                        "区间": label,
                        "年份": year,
                        "年度收益": f"{year_ret:.2%}",
                        "交易笔数": trades_cnt,
                        "胜率": f"{win_rate:.2%}" if not pd.isna(win_rate) else "-",
                        "单笔EV": f"{ev:.2%}" if not pd.isna(ev) else "-",
                    })
                except Exception as e:
                    print(f"Error analyzing {name} for {year}: {e}")
            else:
                rows.append({
                    "区间": label,
                    "年份": year,
                    "年度收益": "未完成",
                    "交易笔数": 0,
                    "胜率": "-",
                    "单笔EV": "-",
                })
                
    df = pd.DataFrame(rows)
    # 按区间和年份排序
    df = df.sort_values(by=["区间", "年份"])
    
    # 打印每个区间的明细
    for label in STRATEGIES.values():
        print(f"\n>>> 实验区间: {label} <<<")
        sub_df = df[df["区间"] == label].drop(columns=["区间"])
        print(sub_df.to_markdown(index=False))
        
    # 保存结果到 md
    report_path = os.path.join(ROOT, "bare_runs_analysis", "exp1_yearly_breakdown.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 实验一：低开区间分年度明细评估\n")
        for label in STRATEGIES.values():
            f.write(f"\n## 实验区间: {label}\n\n")
            sub_df = df[df["区间"] == label].drop(columns=["区间"])
            f.write(sub_df.to_markdown(index=False) + "\n")
    print(f"\nYearly breakdown report saved to {report_path}")

if __name__ == "__main__":
    main()
