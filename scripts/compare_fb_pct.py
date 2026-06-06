"""6-8 月 fb_perf / fb_pct / mode 全表对比 JQ vs 本地。"""
import pandas as pd
import re

jq = pd.read_csv("jq_fb_pct.csv")
jq['date'] = jq['date'].str.replace('-', '')

rows = []
for line in open("local_jun_aug.txt", encoding='utf-8').read().splitlines():
    m = re.match(r"(\d{8}) mode=(\w+) fb=(nan|[+-]?[\d.]+)% fb_pct=(nan|[\d.]+)", line)
    if m:
        fb_str = m.group(3)
        pct_str = m.group(4)
        rows.append({
            'date': m.group(1),
            'local_mode': m.group(2),
            'local_fb': float('nan') if fb_str == 'nan' else float(fb_str) / 100,
            'local_fb_pct': float('nan') if pct_str == 'nan' else float(pct_str),
        })
local = pd.DataFrame(rows)
df = pd.merge(jq, local, on='date', how='outer').sort_values('date')

df['fb_pct_diff'] = df['local_fb_pct'] - df['jq_fb_pct']
df['mode_match'] = df['jq_mode'] == df['local_mode']
df['fb_diff'] = df['local_fb'] - df['jq_fb']

# 汇总
print(f"对比天数: {len(df)}")
print(f"mode 一致: {df['mode_match'].sum()}/{len(df)}")
print(f"fb_pct 完全相同: {(df['fb_pct_diff'].abs() < 0.001).sum()}")
print(f"fb_pct 差 ≤0.02: {(df['fb_pct_diff'].abs() <= 0.02).sum()}")
print(f"fb_pct 差 ≤0.05: {(df['fb_pct_diff'].abs() <= 0.05).sum()}")
print(f"fb_pct 差 ≤0.10: {(df['fb_pct_diff'].abs() <= 0.10).sum()}")
print(f"fb_pct 差 >0.10: {(df['fb_pct_diff'].abs() > 0.10).sum()}")
print(f"fb_pct 最大差: {df['fb_pct_diff'].abs().max():.4f}")

print("\n=== 关键分歧日（fb_pct 差 >0.05 或 mode 不同）===")
bad = df[(df['fb_pct_diff'].abs() > 0.05) | (~df['mode_match'])]
print(bad.to_string(index=False))

df.to_csv("compare_fb_pct.csv", index=False)
print(f"\n已写入 compare_fb_pct.csv")
