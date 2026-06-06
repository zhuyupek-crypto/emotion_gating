"""对全 65 天 PFB 差异逐只股票分类根因。

根因分类：
  R2 停牌：JQ 保留停牌行（paused=1, vol=0），hdata 不写入停牌日 → 本地 prev 无数据
  R3 IPO 首日：主板 +44% 首日涨停，本地修复后应可识别；创业板首 5 日无限制跳过
  R4 ST 标签不一致：JQ 视为 ST(5%)，本地未标 ST（hdata 漏收录）
  R5 退市整理期：hdata ST 表保留 ST 标签但实际涨限 10%，本地用 5% 误算
  R7 其他/未知：两端都有数据但涨停判定仍不一致
"""
import re
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, r'D:\Work Space\他山之石\情绪门控\scripts')
from v227_yjj_probe import identify_first_boards, high_limit_series, load_st, load_basic, build_delist_trans_map

DIAG = Path(r"D:\Work Space\他山之石\情绪门控\jq_diag_full.txt")
DAILY = Path(r"D:\Work Space\HData\data\processed\1d_stock")
META = Path(r"D:\Work Space\HData\data\processed\metadata\stock_basic.parquet")


def jq_to_local(c):
    base, suf = c.split('.')
    return base + '.SZ' if suf == 'XSHE' else base + '.SH'


def main():
    # 加载数据
    df21 = pd.read_parquet(DAILY / "2021.parquet")
    df22 = pd.read_parquet(DAILY / "2022.parquet")
    df = pd.concat([df21, df22], ignore_index=True)
    df = df[~df['code'].str.startswith('688')
            & ~df['code'].str.startswith('8')
            & ~df['code'].str.startswith('92')]
    sb = pd.read_parquet(META)
    name_map = dict(zip(sb['code'].astype(str), sb['name'].astype(str)))
    # 优先使用 load_basic（与 v227_yjj_probe 一致）
    list_date_map_full, _nm, list_status_map, delist_map_full = load_basic()
    list_date_map = list_date_map_full
    delist_map = delist_map_full
    st_map = load_st([2021, 2022])

    tds = sorted(df['date'].unique())
    # 退市整理期股票集合
    delist_trans_map = build_delist_trans_map(list_status_map, delist_map, tds)

    # 解析 JQ PFB
    jq_pfb_re = re.compile(r"\[DIAG-PFB\]\s+(\d{4}-\d{2}-\d{2})\s+n=(\d+)\s+codes=(\S*)")
    jq_pfb = {}
    for line in DIAG.read_text(encoding='utf-8').splitlines():
        m = jq_pfb_re.search(line)
        if m:
            d = m.group(1).replace('-', '')
            jq_pfb[d] = set(m.group(3).split(',')) if m.group(3) else set()

    # 对每个日期对比 + 分类
    rows = []
    for today in sorted(jq_pfb.keys()):
        if today not in tds:
            continue
        i = tds.index(today)
        if i < 2:
            continue
        prev, prev2 = tds[i-1], tds[i-2]
        st_prev = st_map.get(prev, set())
        st_prev2 = st_map.get(prev2, set())
        dt_prev = delist_trans_map.get(prev, set())
        dt_prev2 = delist_trans_map.get(prev2, set())
        d1 = df[df['date']==prev].set_index('code')
        d2 = df[df['date']==prev2].set_index('code')
        local_fbs = identify_first_boards(d1, d2, st_prev, st_prev2, tol=0.02,
                                          d1_date=prev, list_date_map=list_date_map,
                                          dt1=dt_prev, dt2=dt_prev2)
        local_jq = {('{}.XSHE' if c.endswith('.SZ') else '{}.XSHG').format(c[:-3]) for c in local_fbs}

        jq_set = jq_pfb[today]
        jq_only = jq_set - local_jq
        local_only = local_jq - jq_set

        # 分类每只 JQ-only
        for jc in sorted(jq_only):
            lc = jq_to_local(jc)
            name = name_map.get(lc, '')
            ld = list_date_map.get(lc, '')
            dd = delist_map.get(lc, '')
            in_prev = lc in d1.index
            in_prev2 = lc in d2.index

            reason = ''
            in_dt_prev = lc in dt_prev
            in_dt_prev2 = lc in dt_prev2
            if not in_prev2:
                # prev2 缺数据
                if ld and len(ld) == 8 and prev2 < ld:
                    if ld == prev:
                        reason = f'R3 IPO首日@prev (上市={ld})，本地修复后应已识别'
                    else:
                        reason = f'R3 新股未上市@prev2 (上市={ld})'
                else:
                    reason = f'R2 停牌/hdata缺 prev2 数据 (list_date={ld})'
            elif not in_prev:
                if ld and len(ld) == 8 and prev < ld:
                    reason = f'R3 新股未上市@prev (上市={ld})'
                else:
                    reason = f'R2 停牌/hdata缺 prev 数据 (list_date={ld})'
            else:
                # 双日都有数据，看涨停判定
                close_p = round(float(d1.loc[lc, 'close']), 2)
                pre_p = float(d1.loc[lc, 'pre_close'])
                close_pp = round(float(d2.loc[lc, 'close']), 2)
                pre_pp = float(d2.loc[lc, 'pre_close'])
                hl_p = high_limit_series(pd.Series([pre_p], index=[lc]), st_prev, dt_prev).iloc[0]
                hl_pp = high_limit_series(pd.Series([pre_pp], index=[lc]), st_prev2, dt_prev2).iloc[0]
                chg_p = (close_p / pre_p - 1) * 100
                diff_p = abs(int(round(close_p*100)) - int(round(hl_p*100)))
                diff_pp = abs(int(round(close_pp*100)) - int(round(hl_pp*100)))
                at_limit_p = diff_p <= 1
                at_limit_pp = diff_pp <= 1
                in_st = lc in st_prev
                # JQ 把它视为首板，本地没识别
                if at_limit_p and at_limit_pp:
                    reason = f'本地连板≥2 (prev2 也涨停)，但 JQ 算首板（JQ 数据 prev2 不涨停？）'
                elif not at_limit_p:
                    # 5% / 10% / 20% / 44% 都试一下
                    from v227_yjj_probe import _jq_round_limit
                    hl_5 = _jq_round_limit(pre_p, 105, 100)
                    hl_10 = _jq_round_limit(pre_p, 110, 100)
                    hl_20 = _jq_round_limit(pre_p, 120, 100)
                    hl_44 = _jq_round_limit(pre_p, 144, 100)
                    diff_5 = abs(int(round(close_p*100)) - int(round(hl_5*100)))
                    diff_10 = abs(int(round(close_p*100)) - int(round(hl_10*100)))
                    diff_20 = abs(int(round(close_p*100)) - int(round(hl_20*100)))
                    diff_44 = abs(int(round(close_p*100)) - int(round(hl_44*100)))
                    if diff_5 <= 2 and in_st and not in_dt_prev:
                        reason = f'R4 JQ视为ST(5%)涨停，本地non-ST hl={hl_10} | name={name} delist={dd}'
                    elif diff_10 <= 2 and in_dt_prev:
                        reason = f'R5 退市整理期(10%)—hdata ST 标签误判为 5% | name={name} dt_prev={in_dt_prev}'
                    elif diff_44 <= 2 and ld == prev:
                        reason = f'R3 IPO首日+44%涨停，本地修复后应已识别 | name={name}'
                    elif diff_5 <= 2:
                        reason = f'R4 close≈5%限 但本地用{int(hl_p*100)}分 | in_st={in_st} in_dt={in_dt_prev} name={name}'
                    elif diff_10 <= 2:
                        reason = f'R7 close≈10%限 但本地算非涨停 close={close_p} hl={hl_p} in_st={in_st} in_dt={in_dt_prev}'
                    elif diff_20 <= 2:
                        reason = f'R7 close≈20%限 but local=non-limit close={close_p} chg={chg_p:.2f}% gem={lc.startswith("30")}'
                    else:
                        reason = f'R7 prev不涨停 close={close_p} pre={pre_p:.4f} chg={chg_p:.2f}% hl_p={hl_p} in_st={in_st} in_dt={in_dt_prev}'
                else:
                    reason = f'R7 未知 close_p={close_p} hl_p={hl_p} at_limit_p={at_limit_p} at_limit_pp={at_limit_pp}'

            rows.append({
                'today': today, 'code': lc, 'side': 'JQ-only',
                'name': name, 'list_date': ld, 'delist': dd,
                'in_prev': in_prev, 'in_prev2': in_prev2, 'reason': reason,
            })

        for jc in sorted(local_only):
            lc = jq_to_local(jc)
            name = name_map.get(lc, '')
            rows.append({
                'today': today, 'code': lc, 'side': 'local-only',
                'name': name, 'reason': '本地多识别（待查）',
            })

    out = pd.DataFrame(rows)
    out.to_csv("pfb_diff_classified.csv", index=False, encoding='utf-8-sig')

    # 汇总
    print(f"\n=== 总览 ===")
    print(f"总差异行数: {len(out)}")
    print(f"JQ-only: {(out['side']=='JQ-only').sum()}")
    print(f"local-only: {(out['side']=='local-only').sum()}")

    print(f"\n=== JQ-only 根因分布 ===")
    jq_only = out[out['side']=='JQ-only']
    cats = jq_only['reason'].str[:5].value_counts()
    for k, v in cats.items():
        print(f"  {k}: {v}")

    print(f"\n=== 详细列表（按根因分组）===")
    for cat in sorted(out['reason'].str[:5].unique()):
        sub = out[out['reason'].str.startswith(cat)]
        print(f"\n--- {cat} ({len(sub)} 行) ---")
        for _, r in sub.head(15).iterrows():
            print(f"  {r['today']} {r['code']} ({r['name'][:8]}) {r['side']}: {r['reason'][:100]}")

if __name__ == '__main__':
    main()
