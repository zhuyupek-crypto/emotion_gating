from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="coordination/attribution/master_phase1a")
    args = parser.parse_args()
    root = Path(args.out_dir)
    parity = json.loads((root / "BEHAVIOR_PARITY.json").read_text(encoding="utf-8"))
    mapping = json.loads((root / "MAPPING_AUDIT.json").read_text(encoding="utf-8"))
    print(json.dumps({"parity": parity, "mapping": mapping}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
