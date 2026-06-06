from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HDATA_ROOT = Path(r"D:\work space\hdata\data\processed")
YEARS = ["2020", "2021", "2022", "2023"]
PREFIX = "research_train_{year}_force_v227"
OUT_PREFIX = ROOT / "research_train_2020_2023_force_v227"
INIT_CASH = 1_000_000.0


def pct(x: float) -> str:
    if pd.isna(x):
        return ""
    return f"{x:.2%}"


def load_year(year: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = ROOT / PREFIX.format(year=year)
    trades = pd.read_csv(base.with_name(base.name + "_trades.csv"), dtype={"date": str, "entry_date": str})
    equity = pd.read_csv(base.with_name(base.name + "_equity.csv"), dtype={"date": str})
    state = pd.read_csv(base.with_name(base.name + "_state.csv"), dtype={"date": str})
    trades["year"] = year
    equity["year"] = year
    state["year"] = year
    return trades, equity, state


def summarize_equity(equity: pd.DataFrame) -> dict[str, float | int]:
    eq = equity.copy()
    eq["equity"] = eq["equity"].astype(float)
    equity_path = pd.concat(
        [pd.Series([INIT_CASH], dtype=float), eq["equity"].reset_index(drop=True)],
        ignore_index=True,
    )
    peak = equity_path.cummax()
    dd = equity_path / peak - 1
    return {
        "days": len(eq),
        "return": eq["equity"].iloc[-1] / INIT_CASH - 1,
        "max_drawdown": float(dd.min()),
        "end_equity": float(eq["equity"].iloc[-1]),
    }


def summarize_sells(sells: pd.DataFrame) -> dict[str, float | int]:
    if sells.empty:
        return {
            "sells": 0,
            "win_rate": np.nan,
            "avg_trade": np.nan,
            "median_trade": np.nan,
            "best": np.nan,
            "worst": np.nan,
        }
    ret = sells["ret"].astype(float)
    return {
        "sells": len(sells),
        "win_rate": float((ret > 0).mean()),
        "avg_trade": float(ret.mean()),
        "median_trade": float(ret.median()),
        "best": float(ret.max()),
        "worst": float(ret.min()),
    }


def enrich_sells(trades: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    buys = trades[trades["side"] == "buy"].copy()
    sells = trades[trades["side"] == "sell"].copy()

    buy_cols = ["year", "date", "code", "price", "shares", "reason"]
    buys = buys[buy_cols].rename(
        columns={
            "date": "entry_date",
            "price": "entry_price",
            "shares": "entry_shares",
            "reason": "entry_reason",
        }
    )
    buys["entry_price_round"] = buys["entry_price"].round(4)
    sells["entry_price_round"] = sells["entry"].round(4)

    sells = sells.merge(
        buys,
        on=["year", "entry_date", "code", "entry_price_round"],
        how="left",
    )

    state_cols = [
        "year",
        "date",
        "prev",
        "raw_market_mode",
        "market_mode",
        "first_board_perf",
        "fb_pct",
        "active",
        "buy_block",
        "first_boards_n",
        "base_n",
        "v130_n",
        "bear_n",
    ]
    state = state[[c for c in state_cols if c in state.columns]].rename(columns={"date": "entry_date"})
    sells = sells.merge(state, on=["year", "entry_date"], how="left")
    sells = add_entry_gap(sells)

    sells["fb_pct_bucket"] = pd.cut(
        sells["fb_pct"].astype(float),
        bins=[-np.inf, 0.2, 0.4, 0.6, 0.8, np.inf],
        labels=["<=20%", "20-40%", "40-60%", "60-80%", ">80%"],
    )
    sells["entry_gap_bucket"] = pd.cut(
        sells["entry_gap"].astype(float),
        bins=[-np.inf, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, np.inf],
        labels=["<-4%", "-4~-2%", "-2~0%", "0~2%", "2~4%", "4~6%", ">6%"],
    )
    return sells


def add_entry_gap(sells: pd.DataFrame) -> pd.DataFrame:
    out = sells.copy()
    out["prev"] = out["prev"].astype(str)
    years = sorted({int(y) for y in out["year"].dropna().astype(str).unique()})
    frames = []
    for year in years:
        path = HDATA_ROOT / "1d_stock" / f"{year}.parquet"
        frames.append(pd.read_parquet(path, columns=["date", "code", "close"]))
    daily = pd.concat(frames, ignore_index=True)
    daily["date"] = daily["date"].astype(str)
    daily["code"] = daily["code"].str.replace(".SZ", ".XSHE", regex=False)
    daily["code"] = daily["code"].str.replace(".SH", ".XSHG", regex=False)
    prev_close = daily.rename(columns={"date": "prev", "close": "prev_close"})
    prev_close = prev_close[["prev", "code", "prev_close"]]
    out = out.merge(prev_close, on=["prev", "code"], how="left")
    out["entry_gap"] = out["entry_price"].astype(float) / out["prev_close"].astype(float) - 1
    return out


def grouped(sells: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for key, group in sells.groupby(by, dropna=False, observed=False):
        row = {by: "NA" if pd.isna(key) else key}
        row.update(summarize_sells(group))
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["sells", "avg_trade"], ascending=[False, False])
    return out


def monthly_returns(equity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in equity.groupby("year"):
        eq = group.copy()
        eq["month"] = eq["date"].str.slice(0, 6)
        for month, m in eq.groupby("month"):
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "return": m["equity"].iloc[-1] / m["equity"].iloc[0] - 1,
                    "end_equity": m["equity"].iloc[-1],
                    "days": len(m),
                }
            )
    return pd.DataFrame(rows)


def monthly_trade_summary(sells: pd.DataFrame, branch: str | None = None) -> pd.DataFrame:
    data = sells.copy()
    if branch is not None:
        data = data[data["entry_reason"] == branch].copy()
    if data.empty:
        return pd.DataFrame()
    data["month"] = data["entry_date"].astype(str).str.slice(0, 6)
    rows = []
    for month, group in data.groupby("month"):
        row = {"month": month}
        row.update(summarize_sells(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["avg_trade", "sells"], ascending=[True, False])


def filter_cases_yjj(yjj: pd.DataFrame) -> pd.DataFrame:
    gap = yjj["entry_gap_bucket"].astype(str)
    fb = yjj["fb_pct"].astype(float)
    cases = {
        "all_yjj": pd.Series(True, index=yjj.index),
        "drop_fb_le20": fb > 0.2,
        "drop_gap_2_4": gap != "2~4%",
        "drop_gap_gt6": gap != ">6%",
        "drop_gap_2_4_gt6": ~gap.isin(["2~4%", ">6%"]),
        "drop_cautious": yjj["market_mode"] != "cautious",
        "drop_cautious_and_bad_gap": (yjj["market_mode"] != "cautious") & (~gap.isin(["2~4%", ">6%"])),
        "keep_fb_20_40_or_gap_4_6": (fb > 0.2) & (fb <= 0.4) | (gap == "4~6%"),
    }
    rows = []
    for name, mask in cases.items():
        group = yjj[mask]
        row = {"case": name}
        row.update(summarize_sells(group))
        rows.append(row)
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, pct_cols: list[str]) -> str:
    view = df.copy()
    for col in pct_cols:
        if col in view.columns:
            view[col] = view[col].map(pct)
    return view.to_markdown(index=False)


def main() -> None:
    trades_list = []
    equity_list = []
    state_list = []
    for year in YEARS:
        trades, equity, state = load_year(year)
        trades_list.append(trades)
        equity_list.append(equity)
        state_list.append(state)

    trades = pd.concat(trades_list, ignore_index=True)
    equity = pd.concat(equity_list, ignore_index=True)
    state = pd.concat(state_list, ignore_index=True)
    sells = enrich_sells(trades, state)

    yearly_rows = []
    for year in YEARS:
        row = {"year": year}
        row.update(summarize_equity(equity[equity["year"] == year]))
        row.update(summarize_sells(sells[sells["year"] == year]))
        yearly_rows.append(row)
    yearly = pd.DataFrame(yearly_rows)

    all_row = {"year": "all_years_reset"}
    all_row.update(
        {
            "days": int(yearly["days"].sum()),
            "return": float(np.prod(1 + yearly["return"].astype(float)) - 1),
            "max_drawdown": np.nan,
            "end_equity": np.nan,
        }
    )
    all_row.update(summarize_sells(sells))
    yearly = pd.concat([yearly, pd.DataFrame([all_row])], ignore_index=True)

    by_branch = grouped(sells, "entry_reason")
    by_exit = grouped(sells, "reason")
    by_mode = grouped(sells, "market_mode")
    by_fbpct = grouped(sells, "fb_pct_bucket")
    by_gap = grouped(sells, "entry_gap_bucket")
    yjj = sells[sells["entry_reason"] == "v227_yjj"].copy()
    yjj_by_year = grouped(yjj, "year")
    yjj_by_mode = grouped(yjj, "market_mode")
    yjj_by_fbpct = grouped(yjj, "fb_pct_bucket")
    yjj_by_gap = grouped(yjj, "entry_gap_bucket")
    yjj_monthly = monthly_trade_summary(sells, "v227_yjj")
    yjj_filter_cases = filter_cases_yjj(yjj)
    monthly = monthly_returns(equity)

    sells.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_sells_enriched.csv"), index=False, encoding="utf-8-sig")
    yearly.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_yearly.csv"), index=False, encoding="utf-8-sig")
    by_branch.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_by_branch.csv"), index=False, encoding="utf-8-sig")
    by_exit.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_by_exit.csv"), index=False, encoding="utf-8-sig")
    by_mode.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_by_mode.csv"), index=False, encoding="utf-8-sig")
    by_fbpct.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_by_fbpct.csv"), index=False, encoding="utf-8-sig")
    by_gap.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_by_entry_gap.csv"), index=False, encoding="utf-8-sig")
    yjj_by_year.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_yjj_by_year.csv"), index=False, encoding="utf-8-sig")
    yjj_by_mode.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_yjj_by_mode.csv"), index=False, encoding="utf-8-sig")
    yjj_by_fbpct.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_yjj_by_fbpct.csv"), index=False, encoding="utf-8-sig")
    yjj_by_gap.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_yjj_by_entry_gap.csv"), index=False, encoding="utf-8-sig")
    yjj_monthly.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_yjj_monthly.csv"), index=False, encoding="utf-8-sig")
    yjj_filter_cases.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_yjj_filter_cases.csv"), index=False, encoding="utf-8-sig")
    monthly.to_csv(OUT_PREFIX.with_name(OUT_PREFIX.name + "_monthly.csv"), index=False, encoding="utf-8-sig")

    md = [
        "# force_v227 Research Baseline",
        "",
        "Scope: local hdata, yearly independent runs, explicit `--force-v227-route --include-scorpion`.",
        "JoinQuant override files are not used in this research baseline.",
        "",
        "## Yearly",
        markdown_table(
            yearly,
            ["return", "max_drawdown", "win_rate", "avg_trade", "median_trade", "best", "worst"],
        ),
        "",
        "## By Entry Branch",
        markdown_table(by_branch, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## By Exit Reason",
        markdown_table(by_exit, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## By Entry Market Mode",
        markdown_table(by_mode, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## By Entry fb_pct Bucket",
        markdown_table(by_fbpct, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## By Entry Gap Bucket",
        markdown_table(by_gap, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## YJJ By Year",
        markdown_table(yjj_by_year, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## YJJ By Entry Market Mode",
        markdown_table(yjj_by_mode, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## YJJ By Entry fb_pct Bucket",
        markdown_table(yjj_by_fbpct, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## YJJ By Entry Gap Bucket",
        markdown_table(yjj_by_gap, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## Worst YJJ Months By Avg Trade",
        markdown_table(yjj_monthly.head(12), ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
        "## YJJ Simple Filter Cases",
        markdown_table(yjj_filter_cases, ["win_rate", "avg_trade", "median_trade", "best", "worst"]),
        "",
    ]
    OUT_PREFIX.with_name(OUT_PREFIX.name + "_summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
