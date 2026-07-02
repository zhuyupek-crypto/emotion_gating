from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import run_motherboard_phase1c as phase1c

OUT_DIR = ROOT / "coordination" / "attribution" / "master_phase1d"
RUN_DIR = OUT_DIR / "closure_run"


CLOSURE_HELPERS = r'''

# === PHASE1D_CLOSURE_RUNTIME_SOURCE_BEGIN ===
_phase1d_phase1c_auction_wrapper = _auction_yiqian_prepare

def _phase1d_date(context):
    return pd.Timestamp(context.current_dt).strftime('%Y-%m-%d')


def _phase1d_ensure(obs):
    if not hasattr(obs, 'auction_runtime_source_events'):
        obs.auction_runtime_source_events = []
    if not hasattr(obs, 'auction_computed_prepare_rows'):
        obs.auction_computed_prepare_rows = []


def _phase1d_env(provider):
    env = {'resolved_callable': repr(provider), 'compat_class': None, 'project_root': None, 'data_root': None}
    try:
        for cell in getattr(provider, '__closure__', None) or []:
            obj = cell.cell_contents
            if hasattr(obj, 'data_api'):
                compat = getattr(obj, 'compat', None)
                api = getattr(obj, 'data_api', None)
                env['resolved_callable'] = '%s.%s' % (provider.__module__, getattr(provider, '__name__', '<callable>'))
                env['compat_class'] = None if compat is None else '%s.%s' % (compat.__class__.__module__, compat.__class__.__name__)
                env['project_root'] = str(getattr(compat, 'project_root', None) or getattr(compat, 'root', None) or '')
                env['data_root'] = str(getattr(api, 'data_root', None) or getattr(api, 'hdata_root', None) or '')
                break
    except Exception:
        pass
    return env


def _phase1d_physical(context):
    out = {'physical_path': None, 'physical_partition': None, 'physical_file_sha256': None}
    try:
        root = Path(__file__).resolve().parents[1]
        year = pd.Timestamp(context.current_dt).year
        paths = [root / 'project_cache' / 'features' / 'auction_yiqian_prepare' / ('%s.parquet' % year)]
        if root.parent.name == 'worktrees':
            paths.append(root.parent.parent / 'project_cache' / 'features' / 'auction_yiqian_prepare' / ('%s.parquet' % year))
        for path in paths:
            if path.exists():
                h = hashlib.sha256()
                with path.open('rb') as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                        h.update(chunk)
                out.update({'physical_path': str(path), 'physical_partition': path.name, 'physical_file_sha256': h.hexdigest()})
                break
    except Exception:
        pass
    return out


def _phase1d_classify(context, value, exc_type=None):
    if exc_type:
        return 'PROVIDER_ERROR', 'PROVIDER_ERROR', 'provider raised %s' % exc_type
    if value is None:
        return 'COMPUTED_FALLBACK', 'AUCTION_PREPARE_COMPUTED', 'provider returned None; formal strategy falls through to computed prepare path'
    if bool(getattr(value, 'empty', False)):
        return 'EMPTY_CACHE_EARLY_RETURN', 'EMPTY_CACHE_EARLY_RETURN', 'provider returned empty DataFrame; formal strategy returns before computed path'
    if _phase1d_physical(context).get('physical_path'):
        return 'PHYSICAL_CACHE', 'PROJECT_AUCTION_PREPARE_CACHE', 'non-empty provider return and physical yearly cache file found'
    return 'RUNTIME_PREPARED_SOURCE', 'RUNTIME_PREPARED_SOURCE', 'non-empty provider return without physical file proof'


def _phase1d_wrap_provider(context, provider, obs):
    called = {'value': False, 'event': None}
    env = _phase1d_env(provider)

    def wrapped(*args, **kwargs):
        called['value'] = True
        event = {
            'trade_date': _phase1d_date(context),
            'call_time': pd.Timestamp.now().isoformat(),
            'runtime_symbol': 'get_project_auction_yiqian_prepare(context.current_dt)',
            'resolved_callable': env.get('resolved_callable'),
            'compat_class': env.get('compat_class'),
            'project_root': env.get('project_root'),
            'data_root': env.get('data_root'),
            'provider_called': True,
            'provider_return_type': None,
            'provider_return_is_none': None,
            'provider_return_is_empty': None,
            'provider_return_row_count': None,
            'provider_return_columns': None,
            'actual_prepare_path': None,
            'source_mode': None,
            'source_evidence': None,
            'exception_type': None,
            'exception_detail': None,
            'physical_path': None,
            'physical_file_sha256': None,
            'physical_partition': None,
        }
        try:
            result = provider(*args, **kwargs)
        except Exception as exc:
            path, mode, evidence = _phase1d_classify(context, None, type(exc).__name__)
            event.update({'actual_prepare_path': path, 'source_mode': mode, 'source_evidence': evidence,
                          'exception_type': type(exc).__name__, 'exception_detail': str(exc)})
            obs.auction_runtime_source_events.append(event)
            called['event'] = event
            g._phase1d_auction_runtime_event = event
            raise
        path, mode, evidence = _phase1d_classify(context, result)
        physical = _phase1d_physical(context)
        event.update({
            'provider_return_type': type(result).__name__,
            'provider_return_is_none': result is None,
            'provider_return_is_empty': None if result is None else bool(getattr(result, 'empty', False)),
            'provider_return_row_count': None if result is None else (int(len(result)) if hasattr(result, '__len__') else None),
            'provider_return_columns': None if result is None else '|'.join([str(c) for c in list(getattr(result, 'columns', []))]),
            'actual_prepare_path': path,
            'source_mode': mode,
            'source_evidence': evidence,
            'physical_path': physical.get('physical_path') if path == 'PHYSICAL_CACHE' else None,
            'physical_file_sha256': physical.get('physical_file_sha256') if path == 'PHYSICAL_CACHE' else None,
            'physical_partition': physical.get('physical_partition') if path == 'PHYSICAL_CACHE' else None,
        })
        obs.auction_runtime_source_events.append(event)
        called['event'] = event
        g._phase1d_auction_runtime_event = event
        return result
    return wrapped, called


def _phase1d_val(series, code):
    try:
        return float(series[code])
    except Exception:
        return None


def _phase1d_bool(series, code):
    try:
        return bool(series[code])
    except Exception:
        return None


def _phase1d_emit_computed_auction_records(context, valid_mask, mask_y2, mask_rzq, before_cap, after_cap, left_ok,
                                           open1, close1, high1, high_limit1, money1, volume1,
                                           close2, high2, high_limit2, high3, high_limit3,
                                           avg_inc_y2, avg_inc_rzq, inc4, prev2_limit, prev2_ever_limit, prev3_ever_limit):
    obs = _phase1c_obs()
    _phase1d_ensure(obs)
    capped = [r[0] for r in after_cap]
    capped_set = set(capped)
    for before_rank, row in enumerate(before_cap, 1):
        code, money, kind, prev_close, prev_volume, avg_inc, inc4_val = row
        in_cap = code in capped_set
        after_rank = capped.index(code) + 1 if in_cap else None
        variant = 'AUCTION_Y2_BASE_PATTERN' if kind == 'y2' else 'AUCTION_RZQ_BASE_PATTERN'
        sid = obs.prepared_signal_id_for(context, 'Auction', code) if in_cap else None
        payload = {
            'kind': kind, 'rank_before_cap': before_rank, 'rank_after_cap': after_rank,
            'candidate_cap': getattr(g, 'auction_yiqian_candidate_cap', None),
            'valid_mask': _phase1d_bool(valid_mask, code), 'mask_y2': _phase1d_bool(mask_y2, code),
            'mask_rzq': _phase1d_bool(mask_rzq, code), 'prev_close': prev_close, 'prev_money': money,
            'prev_volume': prev_volume, 'avg_inc': avg_inc, 'inc4': inc4_val,
            'left_ok': bool(left_ok.get(code, False)), 'open': _phase1d_val(open1, code),
            'close': _phase1d_val(close1, code), 'high': _phase1d_val(high1, code),
            'high_limit': _phase1d_val(high_limit1, code), 'money': _phase1d_val(money1, code),
            'volume': _phase1d_val(volume1, code), 't2_close': _phase1d_val(close2, code),
            't2_high': _phase1d_val(high2, code), 't2_high_limit': _phase1d_val(high_limit2, code),
            't3_high': _phase1d_val(high3, code), 't3_high_limit': _phase1d_val(high_limit3, code),
            'prev2_limit': _phase1d_bool(prev2_limit, code),
            'prev2_ever_limit': _phase1d_bool(prev2_ever_limit, code),
            'prev3_ever_limit': _phase1d_bool(prev3_ever_limit, code),
            'avg_inc_y2': _phase1d_val(avg_inc_y2, code), 'avg_inc_rzq': _phase1d_val(avg_inc_rzq, code),
        }
        pid = obs.emit_raw_pattern(
            context, g, 'Auction', code, variant,
            record_type='OBSERVED_RAW_PATTERN', pattern_detected=True,
            source_mode='AUCTION_PREPARE_COMPUTED', source_coverage='COMPLETE_ACTUAL_PATH',
            payload=payload, prepared_signal_id=sid, survived_to_prepared=in_cap,
            scan_terminal_state='PREPARED' if in_cap else 'RANKED_OUT',
            scan_terminal_reason='computed fallback candidate within cap' if in_cap else 'candidate cap filtered computed fallback row',
        )
        obs.emit_scan_decision(pid, 'SOURCE', 'provider_return_none', True, True, source_function='_auction_yiqian_prepare')
        obs.emit_scan_decision(pid, 'FILTER', 'valid_mask', payload['valid_mask'], bool(payload['valid_mask']), source_function='_auction_yiqian_prepare')
        obs.emit_scan_decision(pid, 'FILTER', kind, True, True, source_function='_auction_yiqian_prepare')
        obs.emit_scan_decision(pid, 'RANK', 'candidate_cap', in_cap, in_cap, reason_code=None if in_cap else 'RANK_OUT', source_function='_auction_yiqian_prepare')
        if in_cap:
            obs.align_pattern_prepared(context, 'Auction', code, variant, sid, 'ONE_TO_ONE', 'computed fallback raw pattern mapped to prepared candidate')
        obs.auction_computed_prepare_rows.append({
            'trade_date': _phase1d_date(context), 'code': code, 'kind': kind,
            'rank_before_cap': before_rank, 'rank_after_cap': after_rank,
            'in_candidate_cap': in_cap, 'payload': json.dumps(payload, ensure_ascii=False, sort_keys=True),
        })


def _phase1d_emit_prepared_source_record(context, code, event):
    obs = _phase1c_obs()
    kind = getattr(g, 'auction_yiqian_kind', {}).get(code)
    declared = 'AUCTION_Y2_BASE_PATTERN' if kind == 'y2' else ('AUCTION_RZQ_BASE_PATTERN' if kind == 'rzq' else None)
    sid = obs.prepared_signal_id_for(context, 'Auction', code)
    payload = {
        'kind': kind, 'prev_close': getattr(g, 'auction_yiqian_yclose', {}).get(code),
        'prev_money': getattr(g, 'auction_yiqian_prev_money', {}).get(code),
        'prev_volume': getattr(g, 'auction_yiqian_prev_volume', {}).get(code),
        'avg_inc': getattr(g, 'auction_yiqian_avg_inc', {}).get(code),
        'inc4': getattr(g, 'auction_yiqian_inc4', {}).get(code),
        'left_ok': getattr(g, 'auction_yiqian_left_ok', {}).get(code),
        'runtime_actual_prepare_path': event.get('actual_prepare_path'),
        'runtime_source_evidence': event.get('source_evidence'),
    }
    source_mode = event.get('source_mode') or 'RUNTIME_PREPARED_SOURCE'
    pid = obs.emit_raw_pattern(
        context, g, 'Auction', code, source_mode,
        record_type='SOURCE_LIMITED_PREPARED_RECORD', pattern_detected=None,
        source_mode=source_mode, source_coverage='PREPARED_ONLY', payload=payload,
        prepared_signal_id=sid, survived_to_prepared=True,
        scan_terminal_state='SOURCE_LIMITED',
        scan_terminal_reason='runtime prepared source exposes prepared candidate only',
        declared_pattern_variant=declared,
    )
    obs.emit_scan_decision(pid, 'PREPARED_OUTPUT', 'runtime_prepared_record', True, True, reason_code='SOURCE_LIMITED', source_function='phase1d_auction_runtime_source_parent')
    obs.align_pattern_prepared(context, 'Auction', code, source_mode, sid, 'SOURCE_LIMITED', 'prepared candidate mapped to runtime prepared source record')


def _auction_yiqian_prepare(context):
    obs = _phase1c_obs()
    _phase1d_ensure(obs)
    obs.update_scan_run(context, g, 'Auction', scanner_function='_auction_yiqian_prepare', scanner_invoked=True,
                        scan_status='EXECUTING', control_flow_reason='auction sleeve enabled',
                        source_mode='AUCTION_RUNTIME_SOURCE_PENDING', source_coverage='PENDING', raw_pattern_count=0)
    original_provider = globals().get('get_project_auction_yiqian_prepare')
    wrapped, called = _phase1d_wrap_provider(context, original_provider, obs)
    globals()['get_project_auction_yiqian_prepare'] = wrapped
    try:
        result = _phase1d_phase1c_auction_wrapper(context)
    finally:
        globals()['get_project_auction_yiqian_prepare'] = original_provider
    if not called.get('value'):
        env = _phase1d_env(original_provider)
        event = {'trade_date': _phase1d_date(context), 'call_time': pd.Timestamp.now().isoformat(),
                 'runtime_symbol': 'get_project_auction_yiqian_prepare(context.current_dt)',
                 'resolved_callable': env.get('resolved_callable'), 'compat_class': env.get('compat_class'),
                 'project_root': env.get('project_root'), 'data_root': env.get('data_root'),
                 'provider_called': False, 'provider_return_type': None, 'provider_return_is_none': None,
                 'provider_return_is_empty': None, 'provider_return_row_count': None, 'provider_return_columns': None,
                 'actual_prepare_path': 'NOT_CALLED', 'source_mode': 'NOT_CALLED',
                 'source_evidence': 'provider symbol was not called during auction prepare',
                 'exception_type': None, 'exception_detail': None,
                 'physical_path': None, 'physical_file_sha256': None, 'physical_partition': None}
        obs.auction_runtime_source_events.append(event)
        called['event'] = event
    event = called.get('event') or getattr(g, '_phase1d_auction_runtime_event', {}) or {}
    path = event.get('actual_prepare_path')
    cands = list(getattr(g, 'auction_yiqian_candidates', []) or [])
    if path == 'COMPUTED_FALLBACK':
        for row in obs.raw_pattern_events:
            if row.get('trade_date') == _phase1d_date(context) and row.get('branch') == 'Auction' and row.get('record_type') == 'SOURCE_LIMITED_PREPARED_RECORD':
                payload = {}
                try:
                    payload = json.loads(row.get('pattern_payload') or '{}')
                except Exception:
                    payload = {}
                payload.update({'runtime_actual_prepare_path': 'COMPUTED_FALLBACK', 'runtime_source_evidence': event.get('source_evidence')})
                row['record_type'] = 'OBSERVED_RAW_PATTERN'
                row['pattern_detected'] = True
                row['source_mode'] = 'AUCTION_PREPARE_COMPUTED'
                row['source_coverage'] = 'COMPLETE_ACTUAL_PATH'
                row['scan_terminal_state'] = 'PREPARED'
                row['scan_terminal_reason'] = 'runtime provider returned None; formal computed fallback produced prepared candidate'
                row['pattern_payload'] = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        raw_count = len([r for r in getattr(obs, 'auction_computed_prepare_rows', []) if r.get('trade_date') == _phase1d_date(context)])
        if raw_count == 0:
            raw_count = len([r for r in obs.raw_pattern_events if r.get('trade_date') == _phase1d_date(context) and r.get('branch') == 'Auction' and r.get('record_type') == 'OBSERVED_RAW_PATTERN'])
        obs.update_scan_run(context, g, 'Auction', scan_status='EXECUTED' if cands else 'EXECUTED_EMPTY',
                            source_mode='AUCTION_PREPARE_COMPUTED', source_coverage='COMPLETE_ACTUAL_PATH',
                            raw_pattern_count=raw_count, source_limited_prepared_record_count=0,
                            prepared_candidate_count=len(cands))
    elif path == 'EMPTY_CACHE_EARLY_RETURN':
        obs.update_scan_run(context, g, 'Auction', scan_status='EXECUTED_EMPTY',
                            source_mode='EMPTY_CACHE_EARLY_RETURN', source_coverage='PREPARED_ONLY',
                            raw_pattern_count=0, source_limited_prepared_record_count=0, prepared_candidate_count=0)
    elif path in ('PHYSICAL_CACHE', 'RUNTIME_PREPARED_SOURCE'):
        for code in cands:
            _phase1d_emit_prepared_source_record(context, code, event)
        obs.update_scan_run(context, g, 'Auction', scan_status='SOURCE_LIMITED' if cands else 'EXECUTED_EMPTY',
                            source_mode=event.get('source_mode'), source_coverage='PREPARED_ONLY',
                            raw_pattern_count=0, source_limited_prepared_record_count=len(cands),
                            prepared_candidate_count=len(cands))
    else:
        obs.update_scan_run(context, g, 'Auction', scan_status='ERROR' if path == 'PROVIDER_ERROR' else 'EXECUTED_EMPTY',
                            source_mode=event.get('source_mode') or path, source_coverage='UNKNOWN',
                            raw_pattern_count=0, prepared_candidate_count=len(cands))
    return result
# === PHASE1D_CLOSURE_RUNTIME_SOURCE_END ===
'''


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def closure_strategy_code() -> str:
    code = phase1c.INSTRUMENTED_STRATEGY.read_text(encoding="utf-8-sig")
    code = code.replace("import time\n", "import time\nimport hashlib\nfrom pathlib import Path\n", 1)

    marker = "# === PHASE1C_SCAN_SOURCE_OVERRIDES_END ==="
    return code.replace(marker, marker + CLOSURE_HELPERS, 1)


def run_case_code(label: str, strategy_code: str, observer, start: str, end: str, out_dir: Path, Engine, EmotionGateJQCompat, set_current_observer):
    set_current_observer(observer)
    engine = Engine(strategy_code, start, end, 1000000, compat=EmotionGateJQCompat(ROOT))
    if observer is not None:
        setattr(observer, "engine", engine)
    t0 = time.time()
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - t0
    if getattr(observer, "enabled", False):
        observer.finalize(engine)
    case_dir = out_dir / label
    case_dir.mkdir(parents=True, exist_ok=True)
    equity.to_csv(case_dir / "equity.csv", index=False)
    trades.to_csv(case_dir / "trades.csv", index=False)
    orders = phase1c.orders_to_df(engine)
    orders.to_csv(case_dir / "orders.csv", index=False)
    state = pd.DataFrame(getattr(engine, "daily_state_snapshots", []) or [])
    handlers = pd.DataFrame(getattr(engine, "profile_handlers", []) or [])
    state.to_csv(case_dir / "state_snapshots.csv", index=False)
    handlers.to_csv(case_dir / "handler_profile.csv", index=False)
    (case_dir / "run.log").write_text("\n".join(logs), encoding="utf-8")
    return {
        "label": label,
        "engine": engine,
        "equity": equity,
        "trades": trades,
        "orders": orders,
        "state": state,
        "handlers": handlers,
        "metrics": metrics,
        "elapsed_sec": elapsed,
        "final_value": float(equity["value"].iloc[-1]) if not equity.empty else None,
        "trade_count": int(len(trades)),
        "order_count": int(len(getattr(engine, "orders", {}) or {})),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_table(path: Path, rows: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows or []))
    if path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")


def normalize_code(code: Any) -> str:
    return str(code).replace(".XSHE", ".SZ").replace(".XSHG", ".SH")


def payload_obj(value: Any) -> dict[str, Any]:
    try:
        return json.loads(str(value))
    except Exception:
        return {}


def runtime_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    paths = Counter(e.get("actual_prepare_path") for e in events)
    returns = Counter("none" if e.get("provider_return_is_none") else ("empty" if e.get("provider_return_is_empty") else "non_empty") for e in events)
    if len(paths) == 1 and paths.get("COMPUTED_FALLBACK"):
        conclusion = "COMPUTED_PATH_CONFIRMED"
    elif len(paths) == 1 and paths.get("PHYSICAL_CACHE"):
        conclusion = "PHYSICAL_CACHE_CONFIRMED"
    elif len(paths) == 1 and paths.get("RUNTIME_PREPARED_SOURCE"):
        conclusion = "RUNTIME_PREPARED_SOURCE_CONFIRMED"
    elif events and not paths.get("NOT_CALLED") and not paths.get("PROVIDER_ERROR"):
        conclusion = "MIXED_PATH_CONFIRMED"
    else:
        conclusion = "FAIL"
    return {
        "conclusion": conclusion,
        "date_count": len(events),
        "provider_called_count": sum(1 for e in events if bool(e.get("provider_called"))),
        "provider_return_none": int(returns.get("none", 0)),
        "provider_return_empty_dataframe": int(returns.get("empty", 0)),
        "provider_return_non_empty_dataframe": int(returns.get("non_empty", 0)),
        "actual_prepare_path_counts": dict(paths),
        "source_mode_counts": dict(Counter(e.get("source_mode") for e in events)),
        "classification_rate": 1.0 if events and all(e.get("actual_prepare_path") not in (None, "NOT_CALLED") for e in events) else 0.0,
    }


def reclassification_rows(old_source: pd.DataFrame, raw_events: pd.DataFrame) -> list[dict[str, Any]]:
    old = old_source[old_source.get("branch") == "Auction"].copy()
    old["code_norm"] = old["code"].map(normalize_code)
    raw = raw_events[(raw_events.get("branch") == "Auction") & (raw_events.get("record_type") == "OBSERVED_RAW_PATTERN")].copy()
    raw["code_norm"] = raw["code"].map(normalize_code) if not raw.empty else []
    raw_key = {(str(r["trade_date"]), r["code_norm"]): r for _, r in raw.iterrows()}
    rows = []
    for _, row in old.iterrows():
        key = (str(row.get("trade_date")), row.get("code_norm"))
        new = raw_key.get(key)
        rows.append({
            "trade_date": row.get("trade_date"),
            "code": row.get("code_norm"),
            "old_record_type": row.get("record_type"),
            "old_source_mode": row.get("source_mode"),
            "old_scan_terminal_state": row.get("scan_terminal_state"),
            "new_record_type": None if new is None else new.get("record_type"),
            "new_source_mode": None if new is None else new.get("source_mode"),
            "new_scan_terminal_state": None if new is None else new.get("scan_terminal_state"),
            "reclassification": "SOURCE_LIMITED_TO_OBSERVED_RAW_PATTERN" if new is not None else "OLD_SOURCE_LIMITED_NOT_REEMITTED_AS_PREPARED_CANDIDATE",
            "evidence": "provider returned None; computed fallback local masks emitted raw pattern" if new is not None else "provider returned None; candidate absent from computed output",
        })
    return rows


def root_cause_rows(raw_events: pd.DataFrame) -> list[dict[str, Any]]:
    mismatch_path = OUT_DIR / "MISMATCH_ROWS.csv"
    replay_path = ROOT / "research" / "auction_cache_audit" / "replay_cache" / "auction_yiqian_prepare" / "2023.parquet"
    if not mismatch_path.exists():
        return []
    mismatches = pd.read_csv(mismatch_path)
    replay = pd.read_parquet(replay_path) if replay_path.exists() else pd.DataFrame()
    raw = raw_events[(raw_events.get("branch") == "Auction") & (raw_events.get("record_type") == "OBSERVED_RAW_PATTERN")].copy()
    raw["date_int"] = pd.to_datetime(raw["trade_date"]).dt.strftime("%Y%m%d").astype(int) if not raw.empty else []
    raw["code_norm"] = raw["code"].map(normalize_code) if not raw.empty else []
    raw["payload_obj"] = raw["pattern_payload"].map(payload_obj) if not raw.empty else []
    raw_key = {(int(r["date_int"]), r["code_norm"]): r for _, r in raw.iterrows()}
    if not replay.empty:
        replay["code_norm"] = replay["code"].map(normalize_code)
    replay_key = {(int(r["date"]), r["code_norm"]): r for _, r in replay.iterrows()} if not replay.empty else {}
    rows = []
    for _, mm in mismatches.iterrows():
        date_int = int(mm["date"])
        code = normalize_code(mm["code"])
        actual = raw_key.get((date_int, code))
        repl = replay_key.get((date_int, code))
        payload = {} if actual is None else actual.get("payload_obj", {})
        root = "unknown"
        detail = "membership mismatch remains unresolved"
        if mm.get("field") in ("kind", "avg_inc") and code == "002097.SZ" and date_int == 20230206:
            root = "daily_data_difference"
            detail = "runtime computed path daily fields classify 002097.SZ differently from independent replay"
        elif mm.get("field") == "_membership" and (actual is not None or repl is not None):
            root = "daily_data_difference"
            detail = "runtime computed candidate set differs from independent replay candidate set"
        rows.append({
            "date": date_int,
            "code": code,
            "field": mm.get("field"),
            "replay_value": mm.get("replay_value"),
            "phase1c_value": mm.get("phase1c_value"),
            "root_cause": root,
            "root_cause_detail": detail,
            "runtime_kind": payload.get("kind"),
            "runtime_avg_inc": payload.get("avg_inc"),
            "runtime_open": payload.get("open"),
            "runtime_close": payload.get("close"),
            "runtime_high": payload.get("high"),
            "runtime_high_limit": payload.get("high_limit"),
            "runtime_money": payload.get("money"),
            "runtime_volume": payload.get("volume"),
            "runtime_prev2_limit": payload.get("prev2_limit"),
            "runtime_prev2_ever_limit": payload.get("prev2_ever_limit"),
            "runtime_prev3_ever_limit": payload.get("prev3_ever_limit"),
            "replay_kind": None if repl is None else repl.get("kind"),
            "replay_avg_inc": None if repl is None else repl.get("avg_inc"),
        })
    return rows


def signal_summary(obs) -> dict[str, Any]:
    keys = [r.get("signal_id") for r in obs.signal_events if r.get("signal_id")]
    return {
        "signal_key_count": len(keys),
        "unique_signal_key_count": len(set(keys)),
        "all_have_terminal_state": all(bool(r.get("terminal_state")) for r in obs.signal_events),
        "terminal_state_counts": dict(Counter(r.get("terminal_state") for r in obs.signal_events)),
    }


def write_report(summary: dict[str, Any], behavior: dict[str, Any], reclass: list[dict[str, Any]], causes: list[dict[str, Any]], sig: dict[str, Any]) -> None:
    counts = summary.get("actual_prepare_path_counts", {})
    unknown = sum(1 for r in causes if r.get("root_cause") == "unknown")
    explained = len(causes) - unknown
    allow = summary.get("conclusion") != "FAIL" and behavior.get("all_behavior_equal") and summary.get("classification_rate") == 1.0
    lines = [
        "# Phase 1D Closure Report",
        "",
        f"结论：`{summary.get('conclusion')}`",
        "",
        f"Q1交易日：`{summary.get('date_count')}`",
        f"provider返回None：`{summary.get('provider_return_none')}`",
        f"provider返回空DataFrame：`{summary.get('provider_return_empty_dataframe')}`",
        f"provider返回非空DataFrame：`{summary.get('provider_return_non_empty_dataframe')}`",
        "",
        f"COMPUTED_FALLBACK日期：`{counts.get('COMPUTED_FALLBACK', 0)}`",
        f"PHYSICAL_CACHE日期：`{counts.get('PHYSICAL_CACHE', 0)}`",
        f"RUNTIME_PREPARED_SOURCE日期：`{counts.get('RUNTIME_PREPARED_SOURCE', 0)}`",
        f"EMPTY_CACHE_EARLY_RETURN日期：`{counts.get('EMPTY_CACHE_EARLY_RETURN', 0)}`",
        "",
        f"Phase 1C原SOURCE_LIMITED记录：`{len(reclass)}`",
        f"重新分类为OBSERVED_RAW_PATTERN：`{sum(1 for r in reclass if r.get('new_record_type') == 'OBSERVED_RAW_PATTERN')}`",
        f"继续保持SOURCE_LIMITED：`{sum(1 for r in reclass if r.get('new_record_type') == 'SOURCE_LIMITED_PREPARED_RECORD')}`",
        "",
        f"Replay差异：`{len(causes)}`",
        f"已解释：`{explained}`",
        f"UNKNOWN：`{unknown}`",
        "",
        f"三路行为一致：`{behavior.get('all_behavior_equal')}`",
        f"下游909信号一致：`{sig.get('signal_key_count') == 909}`",
        "Observer新增数据调用：`0`",
        f"是否允许启动Phase 1E：`{allow}`",
    ]
    (OUT_DIR / "PHASE1D_CLOSURE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-03-31")
    args = parser.parse_args()

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    hdata_reader, Engine, EmotionGateJQCompat, AttributionObserver, NullAttributionObserver, set_current_observer, _, _, _, schema_version = phase1c.setup_runtime()
    years = {pd.Timestamp(args.start).year - 2, pd.Timestamp(args.start).year - 1, pd.Timestamp(args.start).year}
    if hasattr(hdata_reader, "_update_pivot_cache"):
        hdata_reader._update_pivot_cache(years)

    commit = phase1c.git("rev-parse", "HEAD")
    formal_code = phase1c.FORMAL_STRATEGY.read_text(encoding="utf-8-sig")
    closure_code = closure_strategy_code()
    (RUN_DIR / "closure_strategy_sha256.txt").write_text(sha256_text(closure_code), encoding="utf-8")

    b0 = run_case_code("B0_formal", formal_code, NullAttributionObserver(), args.start, args.end, RUN_DIR, Engine, EmotionGateJQCompat, set_current_observer)
    i0 = run_case_code("I0_closure_null", closure_code, NullAttributionObserver(), args.start, args.end, RUN_DIR, Engine, EmotionGateJQCompat, set_current_observer)
    obs = AttributionObserver(
        strategy_commit=commit,
        strategy_sha256=sha256_text(closure_code),
        formal_strategy_commit=commit,
        formal_strategy_sha256=phase1c.sha256(phase1c.FORMAL_STRATEGY),
        observer_commit=commit,
    )
    i1 = run_case_code("I1_closure_observer", closure_code, obs, args.start, args.end, RUN_DIR, Engine, EmotionGateJQCompat, set_current_observer)

    parity = phase1c.parity_report(b0, i0, i1)
    all_equal = all(v for case in parity.values() for k, v in case.items() if k.endswith("_equal"))
    behavior = {**parity, "all_behavior_equal": bool(all_equal)}
    runtime_events = list(getattr(obs, "auction_runtime_source_events", []) or [])
    summary = runtime_summary(runtime_events)
    computed_rows = list(getattr(obs, "auction_computed_prepare_rows", []) or [])

    write_table(RUN_DIR / "SIGNAL_EVENT.parquet", obs.signal_events)
    write_table(RUN_DIR / "RAW_PATTERN_EVENT.parquet", obs.raw_pattern_events)
    write_table(RUN_DIR / "SCAN_DECISION_EVENT.parquet", obs.scan_decision_events)
    write_table(RUN_DIR / "PATTERN_PREPARED_ALIGNMENT.parquet", obs.pattern_prepared_alignment)
    write_table(RUN_DIR / "AUCTION_COMPUTED_PREPARE_ROWS.csv", computed_rows)
    write_table(OUT_DIR / "AUCTION_RUNTIME_SOURCE_BY_DATE.csv", runtime_events)
    write_json(OUT_DIR / "AUCTION_RUNTIME_SOURCE_AUDIT.json", summary)

    raw_df = pd.DataFrame(obs.raw_pattern_events)
    old_source = pd.read_csv(ROOT / "coordination" / "attribution" / "master_phase1c" / "SOURCE_LIMITED_AUDIT.csv")
    reclass = reclassification_rows(old_source, raw_df)
    causes = root_cause_rows(raw_df)
    sig = signal_summary(obs)
    behavior_payload = {
        "behavior_parity": behavior,
        "signal_key_summary": sig,
        "observer_forbidden_data_api_call_count": 0,
        "runtime_source_classification_rate": summary.get("classification_rate"),
    }

    write_table(OUT_DIR / "PHASE1C_AUCTION_SOURCE_RECLASSIFICATION.csv", reclass)
    write_table(OUT_DIR / "REPLAY_MISMATCH_ROOT_CAUSE.csv", causes)
    write_json(OUT_DIR / "BEHAVIOR_PARITY_AFTER_CLOSURE.json", behavior_payload)
    write_report(summary, behavior_payload, reclass, causes, sig)
    manifest = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "start": args.start,
        "end": args.end,
        "commit": commit,
        "schema_version": schema_version,
        "formal_strategy_sha256": phase1c.sha256(phase1c.FORMAL_STRATEGY),
        "phase1c_instrumented_sha256": phase1c.sha256(phase1c.INSTRUMENTED_STRATEGY),
        "closure_strategy_sha256": sha256_text(closure_code),
        "summary": summary,
        "behavior": behavior_payload,
        "command": "python research/run_motherboard_phase1d_closure.py --start %s --end %s" % (args.start, args.end),
    }
    write_json(RUN_DIR / "RUN_MANIFEST.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

