"""Attribution event writer for Phase 1A."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


def _json_default(value):
    try:
        import numpy as np
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
    except Exception:
        pass
    return str(value)


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_table(rows: Iterable[dict], path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(list(rows))
    if path.suffix.lower() == ".parquet":
        try:
            df.to_parquet(path, index=False)
        except Exception:
            csv_fallback = path.with_suffix(".csv")
            df.to_csv(csv_fallback, index=False)
            path = csv_fallback
    else:
        df.to_csv(path, index=False)
    return {
        "path": str(path),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256_file(path),
    }


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
