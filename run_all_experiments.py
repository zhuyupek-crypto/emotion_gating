import os, sys, subprocess

# Project root (directory containing this script)
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Directory containing experiment scripts
EXP_DIR = os.path.join(ROOT, "scorp_optimize", "strategies")

# Experiment script filenames
experiments = [
    "scorp_exp4_B.py",
    "scorp_exp4_C.py",
    "scorp_exp4_D.py",
    "scorp_exp4_E.py",
]

# Ensure logs directory exists
logs_dir = os.path.join(ROOT, "scorp_optimize", "logs")
os.makedirs(logs_dir, exist_ok=True)

for exp in experiments:
    script_path = os.path.join(EXP_DIR, exp)
    log_path = os.path.join(logs_dir, f"{exp}_output.log")
    print(f"Running {exp} -> {log_path}")
    with open(log_path, "w", encoding="utf-8") as log_file:
        result = subprocess.run([sys.executable, script_path], stdout=log_file, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        print(f"{exp} exited with code {result.returncode}. See {log_path} for details.")
    else:
        print(f"{exp} completed successfully.")
