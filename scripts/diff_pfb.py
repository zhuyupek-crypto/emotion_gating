"""对比 JQ 与本地的 prev_first_boards 列表，找差异股票。

JQ PFB 来自 jq_diag_jun.txt（DIAG-PFB 行）。
本地 PFB 用 identify_first_boards(df[prev], df[prev2], set(), set()) 计算。

对每个日期输出：
- JQ-only: JQ 有但本地无（本地漏识别的首板）
- 本地-only: 本地有但 JQ 无（本地多识别的首板）
- 共有数
"""
import re
import sys
import pandas as pd
import numpy as np
from pathlib import Path

DIAG = Path(r"D:\Work Space\他山之石\情绪门控\jq_diag_full.txt")
DAILY_DIR = Path(r"D:\Work Space\HData\data\processed\1d_stock")

# --- 加载本地数据 ---
def load_daily():
    df21 = pd.read_parquet(DAILY_DIR / "2021.parquet")
    df22 = pd.read_parquet(DAILY_DIR / "2022.parquet")
    df = pd.concat([df21, df22], ignore_index=True)
    # 排除：科创板 688、北交所旧 8 开头、北交所新 92/920 开头
    df = df[~df['code'].str.startswith('688')
            & ~df['code'].str.startswith('8')
            & ~df['code'].str.startswith('92')]
    return df

def to_jq_code(c):
    """000001.SZ -> 000001.XSHE; 600000.SH -> 600000.XSHG"""
    base, suf = c.split('.')
    if suf == 'SZ':
        return base + '.XSHE'
    elif suf == 'SH':
        return base + '.XSHG'
    return c

def from_jq_code(c):
    base, suf = c.split('.')
    if suf == 'XSHE':
        return base + '.SZ'
    elif suf == 'XSHG':
        return base + '.SH'
    return c

# --- 计算本地某日的 first_boards（直接调用修复后的 identify_first_boards）---
def calc_local_pfb(df, today, prev_day, prev2_day, st_set_prev, st_set_prev2,
                   dt_prev=None, dt_prev2=None, list_date_map=None):
    """today=今天，prev_day=昨天（板日），prev2_day=前天。
    用修复后的 identify_first_boards + 真实 ST set + 退市整理期修正。"""
    import sys
    sys.path.insert(0, r'D:\Work Space\他山之石\情绪门控\scripts')
    from v227_yjj_probe import identify_first_boards
    d1 = df[df['date'] == prev_day].set_index('code')
    d2 = df[df['date'] == prev2_day].set_index('code')
    # JQ _scan_all 用 0.02（适用于 cautious/bull，6-8 月主要模式）
    fbs = identify_first_boards(d1, d2, st_set_prev, st_set_prev2, tol=0.02,
                                d1_date=prev_day, list_date_map=list_date_map,
                                dt1=dt_prev, dt2=dt_prev2)
    return set(fbs)

# --- 解析 DIAG-PFB 行 ---
def parse_jq_pfb(diag_path):
    pfb = {}
    pat = re.compile(r"\[DIAG-PFB\]\s+(\d{4}-\d{2}-\d{2})\s+n=(\d+)\s+codes=(\S*)")
    for line in diag_path.read_text(encoding='utf-8').splitlines():
        m = pat.search(line)
        if m:
            date = m.group(1).replace('-', '')
            codes = m.group(3).split(',') if m.group(3) else []
            pfb[date] = set(codes)
    return pfb

# --- 交易日历 ---
def trade_dates(df):
    return sorted(df['date'].unique())

def load_st():
    import sys
    sys.path.insert(0, r'D:\Work Space\他山之石\情绪门控\scripts')
    from v227_yjj_probe import load_st as _load_st_probe
    return _load_st_probe([2021, 2022])


def main():
    import sys
    sys.path.insert(0, r'D:\Work Space\他山之石\情绪门控\scripts')
    from v227_yjj_probe import load_basic as _load_basic, build_delist_trans_map as _build_dt

    df = load_daily()
    tds = trade_dates(df)
    jq_pfb = parse_jq_pfb(DIAG)
    st_map = load_st()
    list_date_map, name_map, list_status_map, delist_map = _load_basic()
    # 退市整理期
    delist_trans_map = _build_dt(list_status_map, delist_map, tds)
    print(f"JQ 提供的 PFB 日期数：{len(jq_pfb)}; ST 日期数：{len(st_map)}")

    rows = []
    for today_jq in sorted(jq_pfb.keys()):
        # 找 today 在交易日历中的位置
        if today_jq not in tds:
            print(f"  {today_jq} 不在本地交易日历"); continue
        i = tds.index(today_jq)
        if i < 2: continue
        prev = tds[i-1]
        prev2 = tds[i-2]
        st_prev = st_map.get(prev, set())
        st_prev2 = st_map.get(prev2, set())
        dt_prev = delist_trans_map.get(prev, set())
        dt_prev2 = delist_trans_map.get(prev2, set())
        local_pfb_local_codes = calc_local_pfb(
            df, today_jq, prev, prev2, st_prev, st_prev2,
            dt_prev=dt_prev, dt_prev2=dt_prev2, list_date_map=list_date_map,
        )
        # 转 JQ 代码
        local_pfb_jq = {to_jq_code(c) for c in local_pfb_local_codes}
        jq_set = jq_pfb[today_jq]
        only_jq = jq_set - local_pfb_jq
        only_local = local_pfb_jq - jq_set
        common = jq_set & local_pfb_jq
        rows.append({
            'date': today_jq, 'prev': prev, 'jq_n': len(jq_set),
            'local_n': len(local_pfb_jq), 'common': len(common),
            'jq_only': len(only_jq), 'local_only': len(only_local),
        })
        print(f"{today_jq} (prev={prev}): JQ={len(jq_set)} 本地={len(local_pfb_jq)} 共有={len(common)} JQ独有={len(only_jq)} 本地独有={len(only_local)}")
        if only_jq:
            print(f"  JQ-only ({len(only_jq)}): {sorted(only_jq)}")
        if only_local:
            print(f"  本地-only ({len(only_local)}): {sorted(only_local)}")

    df_out = pd.DataFrame(rows)
    df_out.to_csv("compare_pfb_jun.csv", index=False, encoding='utf-8-sig')
    print("\n输出 compare_pfb_jun.csv")

if __name__ == '__main__':
    main()
