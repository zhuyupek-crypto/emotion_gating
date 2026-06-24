from jqdata import *
import pandas as pd


def probe():
    stock = "002130.XSHE"
    for day in ["2024-03-25", "2024-03-26"]:
        print("\n=== day", day, "===")
        daily = get_price(
            [stock],
            count=3,
            end_date=day,
            frequency="daily",
            fields=["open", "close", "high", "low", "high_limit", "low_limit", "paused"],
            panel=False,
            fill_paused=False,
        )
        print("\n--- daily ---")
        print(daily.to_string(index=False))
        for t in ["11:25", "13:01", "14:50"]:
            dt = day + " " + t + ":00"
            bars = get_price(
                [stock],
                count=5,
                end_date=dt,
                frequency="1m",
                fields=["open", "high", "low", "close"],
                panel=False,
                fill_paused=False,
            )
            print("\n--- minute", dt, "---")
            print(bars.to_string(index=False))


probe()
