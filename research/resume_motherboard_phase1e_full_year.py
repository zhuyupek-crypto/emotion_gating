from __future__ import annotations

import json
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from research import run_motherboard_phase1e as r
from research import run_motherboard_phase1c as phase1c


def main() -> None:
    q1 = json.loads((r.OUT / "Q1_CANONICAL_REGRESSION.json").read_text(encoding="utf-8"))
    if not q1.get("q1_gate_passed"):
        raise SystemExit("Q1 gate is not passed; full-year run is forbidden.")
    hdata_reader, Engine, Compat, AttrObs, NullObs, set_obs, _, _, _, _ = phase1c.setup_runtime()
    years = {2021, 2022, 2023}
    if hasattr(hdata_reader, "_update_pivot_cache"):
        hdata_reader._update_pivot_cache(years)
    commit = r.git("rev-parse", "HEAD")
    formal_code = phase1c.FORMAL_STRATEGY.read_text(encoding="utf-8-sig")
    v1_code = r.V1.read_text(encoding="utf-8")
    formal_sha, v1_sha = r.sha_file(phase1c.FORMAL_STRATEGY), r.sha_file(r.V1)
    full_dir = r.FULL_RUN / "full_year"
    b0f = r.run_case("B0_FULL_YEAR_formal_null", formal_code, NullObs(), "2023-01-01", "2023-12-31", full_dir, Engine, Compat, set_obs)
    i0f = r.run_case("I0_FULL_YEAR_v1_null", v1_code, NullObs(), "2023-01-01", "2023-12-31", full_dir, Engine, Compat, set_obs)
    obs_a = r.new_observer(AttrObs, commit, v1_sha, formal_sha)
    i1a = r.run_case("I1_FULL_YEAR_A_v1_observer", v1_code, obs_a, "2023-01-01", "2023-12-31", full_dir, Engine, Compat, set_obs)
    r.canonicalize_phase1d_source(obs_a)
    r.persist(obs_a, full_dir / "I1_FULL_YEAR_A_facts")
    obs_b = r.new_observer(AttrObs, commit, v1_sha, formal_sha)
    i1b = r.run_case("I1_FULL_YEAR_B_v1_observer", v1_code, obs_b, "2023-01-01", "2023-12-31", full_dir, Engine, Compat, set_obs)
    r.canonicalize_phase1d_source(obs_b)
    r.persist(obs_b, full_dir / "I1_FULL_YEAR_B_facts")
    full = phase1c.parity_report(b0f, i0f, i1a)
    full["all_behavior_equal"] = r.parity_all(full)
    r.write_json(r.OUT / "FULL_YEAR_BEHAVIOR_PARITY.json", {"cases": [r.summary(x) for x in [b0f, i0f, i1a]], "behavior_parity": full, "all_behavior_equal": full["all_behavior_equal"]})
    rep = r.repeatability(obs_a, obs_b)
    r.write_json(r.OUT / "FULL_YEAR_REPEATABILITY.json", rep)
    tables = r.summarize_tables(obs_a, r.OUT, i1a["engine"])
    closure = tables["closure"]
    r.write_json(r.OUT / "PERFORMANCE_AND_CAPACITY.json", {"full_year_cases": [r.summary(x) for x in [b0f, i0f, i1a, i1b]], "event_volume": tables["event_volume"]})
    env = json.loads((r.OUT / "RUNTIME_ENVIRONMENT_MANIFEST.json").read_text(encoding="utf-8"))
    env["protected_sha_after"] = r.protected_hashes()
    protected_ok = env["protected_sha_before"] == env["protected_sha_after"]
    status = "PASS_AND_FREEZE" if full["all_behavior_equal"] and rep["repeatable"] and closure["unresolved_events"] == 0 and closure["duplicate_signal_key_rows"] == 0 and closure["unmapped_trade_rows"] == 0 and protected_ok else "PARTIAL"
    canon = {"status": status, "observer_contract_version": "1.0", "runtime_environment": "CODE_NATIVE_COMPUTED_ENVIRONMENT", "start": "2023-01-01", "end": "2023-12-31", "strategy_sha256": v1_sha, "formal_strategy_sha256": formal_sha, "signal_event_count": tables["event_volume"]["signal_events"], "signal_key_sha256": rep["signal_key_sha256_a"], "terminal_state_sha256": rep["terminal_state_sha256_a"], "source_mode_sha256": rep["source_mode_sha256_a"], "protected_files_unchanged": protected_ok}
    r.write_json(r.OUT / "RUNTIME_ENVIRONMENT_MANIFEST.json", env)
    r.write_reports(status, q1, full, rep, closure, canon)
    r.write_json(r.OUT / "RUN_MANIFEST.json", {"status": status, "generated_at": pd.Timestamp.now().isoformat(), "q1": q1, "full_year_behavior_parity": full, "full_year_repeatability": rep, "closure": closure, "canonical_2023_baseline": canon, "runtime_environment": env})
    print(json.dumps({"status": status, "full_year_behavior_equal": full["all_behavior_equal"], "repeatable": rep["repeatable"], "closure": closure}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

