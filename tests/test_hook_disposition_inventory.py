from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.audit_hook_disposition import (
    PROTECTED_READONLY_PATHS,
    ROOT,
    audit_hook_disposition,
    build_inventory,
    capture_hashes,
)


def test_each_hook_has_unique_id_and_required_classification():
    inventory = build_inventory()
    hook_ids = [row["hook_id"] for row in inventory]
    assert len(hook_ids) == len(set(hook_ids))
    for row in inventory:
        assert row["semantic_type"] in {"market_rule", "data_correction", "jq_platform_behavior", "project_logic", "unknown"}
        assert row["disposition"] in {"move_to_local_quant", "move_to_hdata", "archive_jq_only", "retain_in_project", "investigate"}
        assert row["status"] in {"active", "archive_candidate", "handoff_pending", "investigation_pending", "retain"}


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
        if row["disposition"] != "move_to_hdata":
            assert row["disposition"] == "investigate"


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
    out_dir = ROOT / "coordination" / "hook_disposition"
    assert str(out_dir).endswith("coordination\\hook_disposition") or str(out_dir).endswith("coordination/hook_disposition")
