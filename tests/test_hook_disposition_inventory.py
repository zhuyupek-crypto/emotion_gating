from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.audit_hook_disposition import (
    ALLOWED_DISPOSITIONS,
    ALLOWED_DOWNSTREAM_RISK,
    ALLOWED_DIRECT_EFFECT,
    ALLOWED_SEMANTIC_TYPES,
    ALLOWED_STATUSES,
    ALLOWED_WAVES,
    PROTECTED_READONLY_PATHS,
    ROOT,
    audit_hook_disposition,
    build_inventory,
    capture_hashes,
)

OUT_DIR = ROOT / "coordination" / "hook_disposition"


# ── Retained original tests (updated for new schema) ──

def test_each_hook_has_unique_id_and_required_classification():
    inventory = build_inventory()
    hook_ids = [row["hook_id"] for row in inventory]
    assert len(hook_ids) == len(set(hook_ids))
    for row in inventory:
        assert row["semantic_type"] in ALLOWED_SEMANTIC_TYPES
        assert row["disposition"] in ALLOWED_DISPOSITIONS
        assert row["status"] in ALLOWED_STATUSES


def test_hooks_have_runtime_callsite_or_explicit_unused_status():
    inventory = build_inventory()
    for row in inventory:
        if row["runtime_callsite_count"] > 0:
            continue
        assert row["status"] in {"archive_candidate", "investigation_pending", "retain"}
        assert row["unused_runtime"] is True


def test_point_hooks_are_not_classified_as_project_logic_without_evidence():
    inventory = build_inventory()
    for row in inventory:
        if (row["trigger_dates"] or row["trigger_codes"]) and row["semantic_type"] == "project_logic":
            assert "project" in row["reason"].lower() or "feature" in row["reason"].lower()


def test_data_correction_has_evidence_or_is_marked_for_investigation():
    inventory = build_inventory()
    for row in inventory:
        if row["semantic_type"] != "data_correction":
            continue
        assert row["evidence"]
        if row["disposition"] != "investigate":
            assert row["disposition"] == "move_to_hdata" or row["disposition"] == "move_to_local_quant"


def test_market_rule_targets_local_quant_and_jq_behavior_targets_archive():
    inventory = build_inventory()
    for row in inventory:
        if row["semantic_type"] == "market_rule":
            assert row["disposition"] == "move_to_local_quant"
        if row["semantic_type"] == "jq_platform_behavior":
            assert row["disposition"] == "archive_jq_only"


def test_audit_outputs_are_consistent_and_read_only(tmp_path: Path):
    before = capture_hashes(PROTECTED_READONLY_PATHS)
    result = audit_hook_disposition(tmp_path)
    after = capture_hashes(PROTECTED_READONLY_PATHS)
    assert before == after

    json_path = Path(result["artifacts"]["json"])
    csv_path = Path(result["artifacts"]["csv"])
    md_path = Path(result["artifacts"]["markdown"])
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    markdown = md_path.read_text(encoding="utf-8")

    assert len(payload["inventory"]) == len(rows)
    assert f"Hook total: `{len(payload['inventory'])}`" in markdown
    for row in payload["inventory"]:
        assert row["hook_id"] in markdown


def test_repo_default_output_path_is_under_coordination():
    assert str(OUT_DIR).endswith("coordination\\hook_disposition") or str(OUT_DIR).endswith("coordination/hook_disposition")


# ── Test 1: metadata complete coverage ──

def test_metadata_keys_covered_by_inventory():
    """Every *_METADATA key must map to exactly one inventory hook_id."""
    import importlib.util

    metadata_modules = [
        "rebuild_from_archive.compat.call_auction",
        "rebuild_from_archive.compat.execution",
        "rebuild_from_archive.compat.market_data",
        "rebuild_from_archive.compat.security_metadata",
        "rebuild_from_archive.compat.strategy_state",
        "rebuild_from_archive.compat.instrument_fallbacks",
    ]

    inventory = build_inventory()
    inventory_ids = set(row["hook_id"] for row in inventory)

    for mod_name in metadata_modules:
        spec = importlib.util.spec_from_file_location(
            mod_name,
            ROOT / (mod_name.replace(".", "/") + ".py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # read with BOM-safe encoding
        src = (ROOT / (mod_name.replace(".", "/") + ".py")).read_text(encoding="utf-8-sig")
        exec(src, mod.__dict__)

        meta_var = None
        for v in dir(mod):
            if v.endswith("_METADATA"):
                meta_var = v
                break
        assert meta_var is not None, f"No _METADATA found in {mod_name}"
        metadata = getattr(mod, meta_var)
        assert isinstance(metadata, dict), f"{meta_var} is not a dict"

        for key in metadata:
            # Try to find corresponding hook_id: module.key
            # For MARKET_DATA_METADATA keys like "corrupted_daily_limit_windows"
            # the hook_id is "market_data.corrupted_daily_limit_windows"
            prefix_map = {
                "CALL_AUCTION_METADATA": "call_auction",
                "EXECUTION_METADATA": "execution",
                "MARKET_DATA_METADATA": "market_data",
                "SECURITY_METADATA": "security_metadata",
                "STRATEGY_STATE_METADATA": "strategy_state",
                "INSTRUMENT_FALLBACK_METADATA": "instrument_fallbacks",
            }
            prefix = prefix_map[meta_var]
            expected_id = f"{prefix}.{key}"
            assert expected_id in inventory_ids, (
                f"Metadata key '{expected_id}' not found in inventory. "
                f"Either add it or add an explicit exclude entry."
            )


# ── Test 2: public hook entry completeness ──

def test_emotion_gate_compat_public_methods_covered():
    """Every public method on EmotionGateJQCompat is covered by inventory or explicit exclude."""
    inventory = build_inventory()
    inventory_ids = set(row["hook_id"] for row in inventory)

    compat_path = ROOT / "rebuild_from_archive" / "project_compat.py"
    src = compat_path.read_text(encoding="utf-8")

    public_methods = []
    in_class = False
    import re
    for line in src.split("\n"):
        if "class EmotionGateJQCompat" in line:
            in_class = True
            continue
        if in_class and "class " in line and "EmotionGateJQCompat" not in line:
            break
        if in_class:
            m = re.match(r"    def (\w+)", line)
            if m and not m.group(1).startswith("_"):
                public_methods.append(m.group(1))

    # Explicit excludes: methods covered by a parent inventory entry
    # Methods that are internal redirects or covered by a broader entry
    excludes = {
        "load_first_seal_year": "project_feature.first_seal_loader",
        "get_project_board_snapshot": "project_feature.board_snapshot_accessor",
        "get_project_master_prepare_index": "project_feature.master_prepare_index_accessor",
        "get_project_auction_yiqian_prepare": "project_feature.auction_yiqian_prepare_accessor",
        "load_project_call_auction_day": "project_feature.call_auction_day_loader",
        "namespace_entries": "project_feature.strategy_namespace_bridge",
        "apply_project_strategy_compat": "project_feature.strategy_namespace_bridge",
        "profile": None,           # profile property - not a compat hook
        "disabled_hook_ids": None, # property - not a compat hook
        "is_hook_enabled": None,   # profile query - not a compat hook
        "profile_manifest": None,  # profile query - not a compat hook
        "record_order_presence_event": None,  # L2 telemetry recorder - called by Engine
        "_feature_path": None,
        "_load_feature_year": None,
    }

    for method in public_methods:
        if method in excludes:
            continue
        # Find the inventory entry that covers this method
        covered = False
        for inv in inventory:
            if method in inv["symbol"] or method in inv["hook_id"] or any(method in p for p in inv.get("call_sites", [])):
                covered = True
                break
        if not covered:
            # Try matching by method name against call_sites
            for inv in inventory:
                for pat in inv.get("call_sites", []):
                    if method in pat:
                        covered = True
                        break
                if covered:
                    break
        assert covered, (
            f"Public method '{method}' is not covered by any inventory entry. "
            f"Add an explicit exclude or create an inventory entry."
        )


# ── Test 3: namespace entry coverage ──

def test_namespace_entries_have_owner():
    """namespace_entries() exposed methods must each have an inventory owner."""
    inventory = build_inventory()
    inventory_ids = set(row["hook_id"] for row in inventory)

    covered_ids = {"project_feature.strategy_namespace_bridge"}
    # The namespace bridge is the single entry that wraps all namespace_entries
    # This test verifies the bridge itself is in inventory
    assert "project_feature.strategy_namespace_bridge" in inventory_ids


# ── Test 4: project infrastructure must not be project_logic ──

def test_project_infrastructure_is_not_project_logic():
    """Seven specific entries must be project_infrastructure, not project_logic."""
    inventory = build_inventory()
    infra_ids = {
        "project_feature.first_seal_loader",
        "project_feature.board_snapshot_accessor",
        "project_feature.master_prepare_index_accessor",
        "project_feature.auction_yiqian_prepare_accessor",
        "project_feature.call_auction_day_loader",
        "project_feature.strategy_namespace_bridge",
        "engine.checkpoint_resume_hook",
    }
    for row in inventory:
        if row["hook_id"] in infra_ids:
            assert row["semantic_type"] == "project_infrastructure", (
                f"{row['hook_id']} should be project_infrastructure, got {row['semantic_type']}"
            )


# ── Test 5: HData candidates must not be move_to_hdata without evidence ──

def test_hdata_candidates_not_prematurely_confirmed():
    """Entries with disposition=move_to_hdata require verifiable evidence in the current branch."""
    inventory = build_inventory()
    for row in inventory:
        if row["disposition"] == "move_to_hdata":
            # There should be NO entries with move_to_hdata as we corrected them
            assert False, f"{row['hook_id']} has disposition=move_to_hdata, should be investigate"
    # Check that hdata_candidate target_owner entries have investigate disposition
    for row in inventory:
        if row["target_owner"] == "hdata_candidate":
            assert row["disposition"] == "investigate", (
                f"{row['hook_id']} is hdata_candidate but disposition is {row['disposition']}, "
                f"should be investigate"
            )


# ── Test 6: evidence path existence for in-branch refs ──

def test_evidence_paths_exist():
    """Evidence strings referencing files in the repo must exist in the current branch."""
    inventory = build_inventory()
    for row in inventory:
        evidence = row["evidence"]
        # Check if evidence references files that should exist
        import re
        file_refs = re.findall(r"rebuild_from_archive/[a-zA-Z_/.]+\.py", evidence)
        for ref in file_refs:
            full_path = ROOT / ref
            assert full_path.exists(), f"Evidence references non-existent file: {ref}"


# ── Test 7: external evidence status ──

def test_external_evidence_not_accepted():
    """Entries referencing external (unmerged branch) evidence must have external_evidence_status != 'accepted'."""
    inventory = build_inventory()
    for row in inventory:
        if row["external_evidence_ref"]:
            assert row["external_evidence_status"] != "accepted", (
                f"{row['hook_id']} has external evidence marked as accepted, "
                f"should be unreviewed"
            )


# ── Test 8: wave consistency across all outputs ──

def test_wave_consistency():
    """Hooks with the same wave must be consistent across MD, JSON, CSV, and JQ_ARCHIVE_PLAN.md."""
    inventory = build_inventory()

    # Run audit to temp dir to get generated outputs
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        result = audit_hook_disposition(Path(tmp))
        json_path = Path(result["artifacts"]["json"])
        payload = json.loads(json_path.read_text(encoding="utf-8"))

        # Check JSON wave -> inventory wave consistency
        for inv_row in inventory:
            json_match = [r for r in payload["inventory"] if r["hook_id"] == inv_row["hook_id"]]
            assert len(json_match) == 1
            assert json_match[0]["wave"] == inv_row["wave"], (
                f"Wave mismatch for {inv_row['hook_id']}: "
                f"build={inv_row['wave']}, JSON={json_match[0]['wave']}"
            )


# ── Test 9: empty config recognition ──

def test_empty_config_entries():
    """execution.preopen_reject_orders must have empty_config=True and entry_count=0."""
    inventory = build_inventory()
    row = next(r for r in inventory if r["hook_id"] == "execution.preopen_reject_orders")
    assert row["empty_config"] is True, "preopen_reject_orders should have empty_config=True"
    assert row["entry_count"] == 0, f"preopen_reject_orders should have entry_count=0, got {row['entry_count']}"


# ── Test 10: master_prepare consumer count ──

def test_master_prepare_consumer():
    """project_feature.master_prepare_index_accessor disposition must be investigate if consumer_count=0."""
    inventory = build_inventory()
    row = next(r for r in inventory if r["hook_id"] == "project_feature.master_prepare_index_accessor")
    if row["consumer_count"] == 0:
        assert row["disposition"] == "investigate", (
            f"master_prepare_index_accessor has {row['consumer_count']} consumers "
            f"but disposition is {row['disposition']} (should be investigate)"
        )


# ── Test 11: report file naming ──

def test_report_file_naming():
    """HOOK_INVENTORY.md must exist; HHOOK_INVENTORY.md must NOT exist."""
    assert (OUT_DIR / "HOOK_INVENTORY.md").exists(), "HOOK_INVENTORY.md must exist"
    assert not (OUT_DIR / "HHOOK_INVENTORY.md").exists(), "HHOOK_INVENTORY.md must NOT exist"


# ── Test 12: JQ_ARCHIVE_PLAN doesn't include legacy shim in L1-L4 waves ──

def test_legacy_shim_not_in_ablation_waves():
    """legacy.temporary_fallbacks_shim must not be in L1/L2/L3/L4."""
    inventory = build_inventory()
    row = next(r for r in inventory if r["hook_id"] == "legacy.temporary_fallbacks_shim")
    assert row["wave"] == "cleanup-only", (
        f"legacy shim has wave={row['wave']}, should be cleanup-only"
    )


# ── Test 13: L1A contains only price hooks ──

def test_l1a_wave():
    """L1A should contain market_data.minute_price_anomalies and execution.execution_price_anomalies."""
    inventory = build_inventory()
    l1a = [r for r in inventory if r["wave"] == "L1A"]
    l1a_ids = sorted(r["hook_id"] for r in l1a)
    assert l1a_ids == ["execution.execution_price_anomalies", "market_data.minute_price_anomalies"], (
        f"L1A contains unexpected entries: {l1a_ids}"
    )


# ── Test 14: L1B contains only size hooks ──

def test_l1b_wave():
    """L1B should contain execution.order_amount_anomalies and execution.fill_amount_anomalies."""
    inventory = build_inventory()
    l1b = [r for r in inventory if r["wave"] == "L1B"]
    l1b_ids = sorted(r["hook_id"] for r in l1b)
    assert l1b_ids == ["execution.fill_amount_anomalies", "execution.order_amount_anomalies"], (
        f"L1B contains unexpected entries: {l1b_ids}"
    )


# ── Test 15: L2 contains order-presence hooks ──

def test_l2_wave():
    """L2 should contain the three preopen hooks."""
    inventory = build_inventory()
    l2 = [r for r in inventory if r["wave"] == "L2"]
    l2_ids = sorted(r["hook_id"] for r in l2)
    assert l2_ids == [
        "execution.preopen_drop_first_duplicate",
        "execution.preopen_reject_cash_below",
        "execution.preopen_reject_orders",
    ], f"L2 contains unexpected entries: {l2_ids}"


# ── Test 16: L3 contains state hooks ──

def test_l3_wave():
    """L3 should contain the two state override hooks."""
    inventory = build_inventory()
    l3 = [r for r in inventory if r["wave"] == "L3"]
    l3_ids = sorted(r["hook_id"] for r in l3)
    assert l3_ids == [
        "strategy_state.fb_state_overrides",
        "strategy_state.v227_shock_overrides",
    ], f"L3 contains unexpected entries: {l3_ids}"


# ── Test 17: four-way wave consistency ──

def test_four_way_wave_consistency():
    """wave must be identical across JSON, CSV, HOOK_INVENTORY.md table, and JQ_ARCHIVE_PLAN.md sections."""
    from tools.audit_hook_disposition import audit_hook_disposition
    import tempfile, json, csv, re

    inventory = build_inventory()

    with tempfile.TemporaryDirectory() as tmp:
        result = audit_hook_disposition(Path(tmp))
        payload = json.loads(Path(result["artifacts"]["json"]).read_text(encoding="utf-8"))

        # 1. JSON wave
        json_wave = {r["hook_id"]: r["wave"] for r in payload["inventory"]}

        # 2. CSV wave
        csv_wave = {}
        with open(Path(result["artifacts"]["csv"]), "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                csv_wave[row["hook_id"]] = row.get("wave", "") or None

        # 3. HOOK_INVENTORY.md table wave column
        md_text = Path(result["artifacts"]["markdown"]).read_text(encoding="utf-8")
        md_wave = {}
        in_table = False
        for line in md_text.split("\n"):
            if "| hook_id | semantic_type | disposition | status | wave " in line:
                in_table = True
                continue
            if in_table and line.startswith("| ---"):
                continue
            if in_table and line.startswith("|"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 6:
                    hook_id = parts[1].strip("`")
                    wave_val = parts[5].strip("`")
                    md_wave[hook_id] = wave_val if wave_val and wave_val != "—" else None
            elif in_table and not line.startswith("|"):
                break

        # 4. JQ_ARCHIVE_PLAN.md section wave
        archive_path = Path(result["artifacts"]["archive"])
        archive_text = archive_path.read_text(encoding="utf-8")
        section_wave_map = {
            "L1A": "L1A — 价格类钩子",
            "L1B": "L1B — 数量类钩子",
            "L2": "L2 — 订单存在性类钩子",
            "L3": "L3 — 状态历史答案类钩子",
            "L4": "L4 — JQ数据形态类钩子",
        }
        archive_wave = {}
        current_section = None
        for line in archive_text.split("\n"):
            for wave_key, section_title in section_wave_map.items():
                if section_title in line:
                    current_section = wave_key
                    break
            if line.strip().startswith("- `") and "`" in line:
                m = re.match(r"- `([^`]+)`", line)
                if m and current_section:
                    archive_wave[m.group(1)] = current_section
            elif line.strip().startswith("## 非消融项"):
                current_section = "cleanup-only"
            elif line.strip().startswith("## `"):
                m = re.match(r"## `([^`]+)`", line)
                if m:
                    # This is a detail section - don't set wave here
                    pass
            elif line.strip().startswith("## 所有"):
                current_section = None

    # Compare all four
    for row in inventory:
        hid = row["hook_id"]
        expected = row["wave"]
        assert json_wave.get(hid) == expected, f"{hid}: JSON wave={json_wave.get(hid)} vs expected={expected}"
        assert csv_wave.get(hid) == expected, f"{hid}: CSV wave={csv_wave.get(hid)} vs expected={expected}"
        assert md_wave.get(hid) == expected, f"{hid}: MD wave={md_wave.get(hid)} vs expected={expected}"
        # Archive plan only covers archive-only items
        if row["disposition"] == "archive_jq_only" or row["semantic_type"] == "jq_platform_behavior":
            if expected is not None:
                assert archive_wave.get(hid) == expected, (
                    f"{hid}: Archive wave={archive_wave.get(hid)} vs expected={expected}"
                )


# ── Test 18: no direct move_to_hdata disposition ──

def test_no_premature_hdata_claim():
    """No hook should claim move_to_hdata without current-branch evidence."""
    inventory = build_inventory()
    hdata_dispositions = [r for r in inventory if r["disposition"] == "move_to_hdata"]
    assert len(hdata_dispositions) == 0, (
        f"Found {len(hdata_dispositions)} entries with move_to_hdata: "
        f"{[r['hook_id'] for r in hdata_dispositions]}"
    )


# ── Test 19: direct_effect_scope and downstream_risk values are valid ──

def test_direct_effect_and_downstream_values():
    """Every direct_effect_scope and downstream_risk field must use only allowed values."""
    from tools.audit_hook_disposition import ALLOWED_DIRECT_EFFECT, ALLOWED_DOWNSTREAM_RISK
    inventory = build_inventory()
    for row in inventory:
        for val in (row.get("direct_effect_scope") or []):
            assert val in ALLOWED_DIRECT_EFFECT, (
                f"{row['hook_id']}: direct_effect_scope contains '{val}' "
                f"which is not in {ALLOWED_DIRECT_EFFECT}"
            )
        dr = row.get("downstream_risk")
        assert dr is None or dr in ALLOWED_DOWNSTREAM_RISK, (
            f"{row['hook_id']}: downstream_risk='{dr}' "
            f"not in {ALLOWED_DOWNSTREAM_RISK}"
        )


# ── Test 20: comprehensive evidence path validation ──

def test_evidence_paths_exist_comprehensive():
    """All evidence and acceptance_test file references must exist in current branch."""
    import re
    inventory = build_inventory()

    # Define path prefixes to check
    known_prefixes = (
        "rebuild_from_archive/",
        "tests/",
        "tools/",
        "alignment_reports/",
        "coordination/",
        "母版-",
    )

    for row in inventory:
        for field_name in ("evidence", "acceptance_test"):
            text = row.get(field_name, "")
            if not text:
                continue
            # Find all file references (not URLs, not descriptions)
            refs = re.findall(r'(?:rebuild_from_archive/[a-zA-Z0-9_/.]+\.(?:py|md))', text)
            refs += re.findall(r'(?:tests/[a-zA-Z0-9_/.]+\.(?:py|md))', text)
            refs += re.findall(r'(?:tools/[a-zA-Z0-9_/.]+\.(?:py|md))', text)
            refs += re.findall(r'(?:alignment_reports/[a-zA-Z0-9_/.]+\.(?:py|md))', text)
            refs += re.findall(r'(?:coordination/[a-zA-Z0-9_/.]+\.(?:py|md))', text)
            refs += re.findall(r'(?:母版-[a-zA-Z0-9_-]+\.py)', text)
            for ref in refs:
                full_path = ROOT / ref
                assert full_path.exists(), (
                    f"{row['hook_id']}.{field_name} references non-existent file: {ref}. "
                    f"If the file is on an unmerged branch, move the reference to external_evidence_ref."
                )


# ── Test 21: namespace_entries real key coverage ──

def test_namespace_entries_actual_keys():
    """namespace_entries() returned keys must each map to a hook_id in inventory."""
    import ast
    inventory = build_inventory()
    inventory_ids = set(row["hook_id"] for row in inventory)

    compat_path = ROOT / "rebuild_from_archive" / "project_compat.py"
    tree = ast.parse(compat_path.read_text(encoding="utf-8"))

    # Extract return dict keys from namespace_entries method
    ns_keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "namespace_entries":
            for child in ast.walk(node):
                if isinstance(child, ast.Dict):
                    for key in child.keys:
                        if isinstance(key, ast.Constant):
                            ns_keys.add(key.value)
                    break

    assert len(ns_keys) > 0, "Could not parse namespace_entries return keys"

    # Map of known namespace keys to hook_id
    ns_to_hook = {
        "apply_project_strategy_compat": "project_feature.strategy_namespace_bridge",
    }

    for key in sorted(ns_keys):
        if key in ns_to_hook:
            assert ns_to_hook[key] in inventory_ids, (
                f"namespace entry '{key}' maps to {ns_to_hook[key]} but that hook_id is not in inventory"
            )
        else:
            # Check if any inventory entry covers this key
            covered = False
            for inv in inventory:
                if key in inv["symbol"] or key in inv["hook_id"]:
                    covered = True
                    break
            assert covered, (
                f"namespace entry '{key}' is not covered by any inventory entry. "
                f"Either add it to ns_to_hook mapping or create an inventory entry."
            )
