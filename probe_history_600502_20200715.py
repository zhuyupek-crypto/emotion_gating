import importlib
import os
import sys

import pandas as pd


ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "rebuild_from_archive")
sys.path.insert(0, WORK)
sys.path.insert(1, ROOT)
sys.path.insert(2, r"D:\work space\hdata")
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from engine.core import Engine
from project_compat import EmotionGateJQCompat


strategy_code = """
def initialize(context):
    pass
"""

engine = Engine(strategy_code, "2020-07-01", "2020-07-15", 1000000, compat=EmotionGateJQCompat(ROOT))
engine.context.previous_date = pd.Timestamp("2020-07-14")
engine.context.current_dt = pd.Timestamp("2020-07-15 11:25")
engine.current_time = "11:25"
df = engine.wrapped_history(5, unit="1d", field="close", security_list=["600502.XSHG"])
print(df)
print("mean", df.mean().to_dict())

