from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rebuild_from_archive.compat.call_auction import (  # noqa: E402
    CALL_AUCTION_ALLOW_ONLY,
    CALL_AUCTION_DEPTH_OVERRIDES,
    CALL_AUCTION_EMPTY_ANOMALIES,
)
from rebuild_from_archive.compat.execution import (  # noqa: E402
    EXECUTION_PRICE_ANOMALIES,
    FILL_AMOUNT_ANOMALIES,
    ORDER_AMOUNT_ANOMALIES,
    PREOPEN_DROP_FIRST_DUPLICATE,
    PREOPEN_REJECT_CASH_BELOW,
    PREOPEN_REJECT_ORDERS,
)
from rebuild_from_archive.compat.instrument_fallbacks import (  # noqa: E402
    INSTRUMENT_PRICE_FALLBACKS,
    ZERO_FEE_OVERRIDES,
)
from rebuild_from_archive.compat.market_data import (  # noqa: E402
    CORRUPTED_DAILY_LIMIT_WINDOWS,
    DAILY_FIELD_ANOMALIES,
    DAILY_IPO_CLOSE_ANOMALIES,
    MINUTE_PRICE_ANOMALIES,
    TAIL_SEAL_ANOMALIES,
)
from rebuild_from_archive.compat.security_metadata import (  # noqa: E402
    BILLBOARD_ROW_FILTERS,
    NON_ST_NAME_WINDOWS,
    SECURITY_START_DATE_OVERRIDES,
)
from rebuild_from_archive.compat.strategy_state import (  # noqa: E402
    FB_STATE_OVERRIDES,
    V227_SHOCK_OVERRIDES,
)

SEARCH_PATHS = [
    "rebuild_from_archive/compat",
    "rebuild_from_archive/project_compat.py",
    "rebuild_from_archive/engine",
    "rebuild_from_archive/project_preprocess.py",
    "rebuild_from_archive/data_api.py",
    "rebuild_from_archive/legacy",
    "母版-20260506-Clone.py",
    "tests",
    "tools",
    "alignment_reports",
]

PRIMARY_RUNTIME_PREFIXES = (
    "rebuild_from_archive/engine/",
    "rebuild_from_archive/project_compat.py",
    "rebuild_from_archive/project_preprocess.py",
    "rebuild_from_archive/data_api.py",
    "母版-20260506-Clone.py",
)

PROTECTED_READONLY_PATHS = [
    ROOT / "rebuild_from_archive" / "project_compat.py",
    ROOT / "rebuild_from_archive" / "engine" / "core.py",
    ROOT / "rebuild_from_archive" / "engine" / "data_api.py",
    ROOT / "rebuild_from_archive" / "project_preprocess.py",
    ROOT / "rebuild_from_archive" / "data_api.py",
    ROOT / "母版-20260506-Clone.py",
]

DATE_TOKEN_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2}|20\d{6}|1900-01-01)\b")
CODE_TOKEN_RE = re.compile(r"\b\d{6}\.(?:XSHE|XSHG|SZ|SH|BJ)\b")

ALLOWED_SEMANTIC_TYPES = {
    "market_rule", "data_correction", "jq_platform_behavior",
    "project_logic", "project_infrastructure", "unknown",
}
ALLOWED_DISPOSITIONS = {
    "move_to_local_quant", "move_to_hdata", "archive_jq_only",
    "retain_in_project", "investigate",
}
ALLOWED_STATUSES = {
    "active", "archive_candidate", "handoff_pending",
    "investigation_pending", "retain",
}
ALLOWED_WAVES = {"L1A", "L1B", "L2", "L3", "L4", "cleanup-only", None}
ALLOWED_DIRECT_EFFECT = {"none", "price", "size", "order_presence", "state", "selection", "data_shape", "infrastructure", "cash_settlement", "fee"}
ALLOWED_DOWNSTREAM_RISK = {"none", "nav_only", "cash_path", "position_path", "strategy_path", "unknown"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256_file(path) for path in paths if path.exists()}


def count_items(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (dict, set, list, tuple)):
        return len(value)
    return 1


def flatten_tokens(value: Any) -> list[str]:
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, dict):
        for k, v in value.items():
            out.extend(flatten_tokens(k))
            out.extend(flatten_tokens(v))
        return out
    if isinstance(value, (list, tuple, set)):
        for item in value:
            out.extend(flatten_tokens(item))
        return out
    if hasattr(value, "isoformat"):
        try:
            out.append(str(value.isoformat()))
            return out
        except Exception:
            pass
    out.append(str(value))
    return out


def normalize_dates(values: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for value in values:
        for token in DATE_TOKEN_RE.findall(value):
            token = token.replace("/", "-")
            if len(token) == 8 and token.isdigit():
                token = f"{token[:4]}-{token[4:6]}-{token[6:]}"
            if token not in seen:
                seen.add(token)
                out.append(token)
    return sorted(out)


def normalize_codes(values: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for value in values:
        for token in CODE_TOKEN_RE.findall(value):
            if token not in seen:
                seen.add(token)
                out.append(token)
    return sorted(out)


def years_from_dates(trigger_dates: list[str]) -> list[int]:
    years = set()
    for date_text in trigger_dates:
        m = re.match(r"(\d{4})", date_text)
        if m:
            years.add(int(m.group(1)))
    return sorted(years)


def list_to_text(values: list[Any]) -> str:
    return "; ".join(str(v) for v in values) if values else ""


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def rg_fixed(pattern: str) -> list[str]:
    cmd = [
        "rg",
        "-n",
        "--fixed-strings",
        pattern,
        *SEARCH_PATHS,
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return lines


def collect_call_sites(patterns: list[str]) -> tuple[list[str], list[str]]:
    runtime_hits: list[str] = []
    secondary_hits: list[str] = []
    seen_runtime = set()
    seen_secondary = set()
    for pattern in patterns:
        for line in rg_fixed(pattern):
            path_part = line.split(":", 1)[0].replace("\\", "/")
            if path_part.startswith(PRIMARY_RUNTIME_PREFIXES):
                if line not in seen_runtime:
                    seen_runtime.add(line)
                    runtime_hits.append(line)
            else:
                if line not in seen_secondary:
                    seen_secondary.add(line)
                    secondary_hits.append(line)
    return sorted(runtime_hits), sorted(secondary_hits)


def classify_call_lines(lines: list[str]) -> tuple[int, int, int]:
    """Classify a list of rg hit lines into definition/forwarder/consumer counts.
    
    - definition: line contains 'def ' (method/function definition)
    - forwarder: line is a pass-through call that delegates to another method
    - consumer: anything else — actual strategy logic or conditional use
    """
    definitions = 0
    forwarders = 0
    consumers = 0
    for line in lines:
        content = line.split(":", 2)[-1] if line.count(":") >= 2 else ""
        if "def " in content:
            definitions += 1
        elif "return self.compat." in content or "return self.compat." in line:
            forwarders += 1
        elif "return self.data_api." in content or "return self.data_api." in line:
            forwarders += 1
        elif "self.compat." in content and "return" in content:
            forwarders += 1
        elif "engine.data_api." in content and "return" not in content:
            # Namespace forwarding call (no return keyword in lambda)
            forwarders += 1
        elif "self.data_api." in content:
            forwarders += 1
        else:
            consumers += 1
    return definitions, forwarders, consumers


def build_trigger_info(
    data_obj: Any = None,
    manual_dates: list[str] | None = None,
    manual_codes: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    tokens = flatten_tokens(data_obj)
    dates = normalize_dates(tokens)
    codes = normalize_codes(tokens)
    if manual_dates:
        dates = sorted(set(dates) | set(manual_dates))
    if manual_codes:
        codes = sorted(set(codes) | set(manual_codes))
    return dates, codes


@dataclass(frozen=True)
class HookSpec:
    hook_id: str
    module: str
    symbol: str
    data_obj: Any
    affected_fields: list[str]
    behavior: str
    semantic_type: str
    disposition: str
    reason: str
    evidence: str
    affects_selection: bool
    affects_state: bool
    affects_order: bool
    affects_fill: bool
    affects_nav: bool
    target_owner: str
    handoff_requirement: str
    disable_requirement: str
    delete_requirement: str
    acceptance_test: str
    status: str
    call_site_patterns: list[str]
    wave: str | None = None
    direct_effect_scope: list[str] | None = None
    downstream_risk: str | None = None
    empty_config: bool = False
    manual_dates: list[str] | None = None
    manual_codes: list[str] | None = None
    count_override: int | None = None
    external_evidence_ref: str | None = None
    external_evidence_status: str | None = None


HOOK_SPECS: list[HookSpec] = [
    HookSpec(
        hook_id="engine.immediate_sell_cash_release",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.immediate_sell_cash_release",
        data_obj={"immediate_sell_cash_release": True},
        affected_fields=["available_cash", "locked_cash", "positions_value"],
        behavior="Release sell proceeds immediately after fill instead of waiting until end-of-day rollover.",
        semantic_type="market_rule",
        disposition="move_to_local_quant",
        reason="This is account and cash-settlement semantics, not project alpha logic.",
        evidence="rebuild_from_archive/project_compat.py sets immediate_sell_cash_release=True and engine/core.py consumes it in the sell-fill cash path.",
        affects_selection=False,
        affects_state=False,
        affects_order=True,
        affects_fill=True,
        affects_nav=True,
        target_owner="local_quant",
        wave=None,
        direct_effect_scope=["cash_settlement"],
        downstream_risk="cash_path",
        handoff_requirement="local_quant needs a first-class switch for sell-cash release timing so project code stops carrying the behavior flag.",
        disable_requirement="Disable only after local_quant can reproduce the intended cash-release policy in native mode.",
        delete_requirement="Delete when engine/core.py no longer checks compat.immediate_sell_cash_release and the policy lives in local_quant.",
        acceptance_test="Inventory-only: verify engine/core.py still references immediate_sell_cash_release and classify it as local_quant-owned.",
        status="handoff_pending",
        call_site_patterns=["immediate_sell_cash_release"],
    ),
    HookSpec(
        hook_id="market_data.corrupted_daily_limit_windows",
        module="rebuild_from_archive.compat.market_data",
        symbol="CORRUPTED_DAILY_LIMIT_WINDOWS",
        data_obj=CORRUPTED_DAILY_LIMIT_WINDOWS,
        affected_fields=["pre_close", "high_limit", "low_limit", "money", "volume", "board_snapshot", "first_seal_time"],
        behavior="Quarantine a known daily-data corruption window by bypassing fast-path history and suppressing selected cached features.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="The 2026 corruption window is a source-data quality concern, but the full root cause and impact scope have not yet been independently verified. JQ vs local data difference possible.",
        evidence="Project currently has an explicit data isolation window used at runtime to bypass fast-path and caching. The root cause and full impact range still need HData audit confirmation.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=True,
        target_owner="hdata_candidate",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="HData or upstream cache metadata must publish corruption windows and field-level quarantine signals.",
        disable_requirement="Disable only after raw-data quality flags propagate through cache build and runtime readers.",
        delete_requirement="Delete after HData versioned quality metadata replaces project-specific date guards and all dependent caches respect the same rule.",
        acceptance_test="External investigation branch codex/data-quality-propagation-audit at commit b951d3885f09fcc6d455675799a295c569af5439 (not accepted/not merged); requires verification via hdata_candidate queue",
        status="investigation_pending",
        call_site_patterns=["should_bypass_history_fastpath(", "load_first_seal_year(", "get_project_board_snapshot("],
        external_evidence_ref="codex/data-quality-propagation-audit branch, commit b951d3885f09fcc6d455675799a295c569af5439",
        external_evidence_status="unreviewed",
    ),
    HookSpec(
        hook_id="market_data.tail_seal_anomalies",
        module="rebuild_from_archive.compat.market_data",
        symbol="TAIL_SEAL_ANOMALIES",
        data_obj=TAIL_SEAL_ANOMALIES,
        affected_fields=["first_limit_hit_time", "seal_bucket", "is_tail_seal"],
        behavior="Inject observed first-seal timestamps when minute-derived first hit times diverge from archived reference runs.",
        semantic_type="unknown",
        disposition="investigate",
        reason="These point fixes may reflect minute-data issues or JoinQuant snapshot behavior; current evidence does not prove the owner.",
        evidence="rebuild_from_archive/project_preprocess.py and engine/data_api.py both honor get_tail_seal_override for the same keyed timestamps.",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="investigation",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Need side-by-side evidence from minute source, derived first-seal cache, and mother reference to decide HData vs JQ archive ownership.",
        disable_requirement="In local-native mode this group can be disabled only after first-seal behavior is proven acceptable without parity timestamps.",
        delete_requirement="Delete after either HData is fixed and caches are rebuilt, or the project explicitly archives JoinQuant-only seal answers.",
        acceptance_test="tests/test_compat_entrypoints.py::test_call_auction_overrides_apply does not cover this hook; add targeted first-seal evidence before retirement.",
        status="investigation_pending",
        call_site_patterns=["get_tail_seal_override("],
    ),
    HookSpec(
        hook_id="market_data.minute_price_anomalies",
        module="rebuild_from_archive.compat.market_data",
        symbol="MINUTE_PRICE_ANOMALIES",
        data_obj=MINUTE_PRICE_ANOMALIES,
        affected_fields=["close", "trade_price"],
        behavior="Override minute-bar trade prices at specific timestamps to reproduce archived buy/sell boundary fills.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="These are point answers for historical JoinQuant parity and do not describe a reusable market rule.",
        evidence="rebuild_from_archive/engine/core.py applies get_minute_price_override inside _apply_jq_minute_price_anomaly before returning trade prices.",
        affects_selection=False,
        affects_state=False,
        affects_order=False,
        affects_fill=True,
        affects_nav=True,
        target_owner="jq_archive",
        wave="L1A",
        direct_effect_scope=["price"],
        downstream_risk="cash_path",
        handoff_requirement="Keep only in the JoinQuant replay profile; do not move into local-native market data behavior.",
        disable_requirement="Safe first-wave disable candidate for local-native mode if some trade price and NAV drift is acceptable.",
        delete_requirement="Delete once the project formally stops supporting JoinQuant minute-fill parity.",
        acceptance_test="tests/test_compat_entrypoints.py::test_minute_and_execution_overrides",
        status="archive_candidate",
        call_site_patterns=["get_minute_price_override("],
    ),
    HookSpec(
        hook_id="market_data.daily_ipo_close_anomalies",
        module="rebuild_from_archive.compat.market_data",
        symbol="DAILY_IPO_CLOSE_ANOMALIES",
        data_obj=DAILY_IPO_CLOSE_ANOMALIES,
        affected_fields=["close", "high_limit", "low_limit", "pre_close"],
        behavior="Patch IPO sync-delay rows where the parity path expects prior close plus trailing NaN behavior.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="This behavior exists to mimic the historical JoinQuant return shape, not to express a stable local market-data rule.",
        evidence="engine/data_api.py applies get_daily_ipo_close_override in both panel and long-form daily-history anomaly patchers.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="jq_archive",
        wave="L4",
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Retain only under a JoinQuant parity profile or archived replay mode.",
        disable_requirement="Can be disabled in local-native mode once IPO handling is expected to follow local data directly.",
        delete_requirement="Delete after the project drops JoinQuant daily-history shape parity.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2020 IPO override checks",
        status="archive_candidate",
        call_site_patterns=["get_daily_ipo_close_override("],
    ),
    HookSpec(
        hook_id="market_data.daily_field_anomalies",
        module="rebuild_from_archive.compat.market_data",
        symbol="DAILY_FIELD_ANOMALIES",
        data_obj=DAILY_FIELD_ANOMALIES,
        affected_fields=["open", "high", "high_limit", "money"],
        behavior="Patch specific daily field values before selection/state logic consumes them.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="Some rows align with proven source corruption, while others are isolated point answers whose root cause is not yet assigned.",
        evidence="engine/data_api.py and engine/core.py both query get_daily_field_override; 2026 high/high_limit overrides are also covered by the data-quality audit.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=True,
        target_owner="investigation",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Split the group into true source-data defects vs JoinQuant-only answers before moving ownership.",
        disable_requirement="Disable only after each remaining point is either archived as JQ-only or repaired upstream.",
        delete_requirement="Delete only after the mixed bundle is decomposed and each member has a final owner.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2026 corrupted daily fastpath check",
        status="investigation_pending",
        call_site_patterns=["get_daily_field_override("],
    ),
    HookSpec(
        hook_id="execution.preopen_reject_cash_below",
        module="rebuild_from_archive.compat.execution",
        symbol="PREOPEN_REJECT_CASH_BELOW",
        data_obj=PREOPEN_REJECT_CASH_BELOW,
        affected_fields=["available_cash", "preopen_order_acceptance"],
        behavior="Reject pre-open orders below a recorded cash threshold at a specific timestamp.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="This is a recorded JoinQuant answer for one historical event, not a general exchange rule.",
        evidence="engine/core.py calls compat.should_reject_preopen_cash inside _should_reject_jq_preopen_order.",
        affects_selection=False,
        affects_state=False,
        affects_order=True,
        affects_fill=False,
        affects_nav=True,
        target_owner="jq_archive",
        wave="L2",
        direct_effect_scope=["order_presence"],
        downstream_risk="strategy_path",
        handoff_requirement="Keep under JQ replay only; local-native mode should not inherit date-specific cash floors.",
        disable_requirement="Safe early-disable candidate when leaving JQ parity, with the expectation that only order acceptance and downstream NAV change.",
        delete_requirement="Delete when JQ pre-open rejection replay is no longer a supported mode.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2025 preopen cash floor check",
        status="archive_candidate",
        call_site_patterns=["should_reject_preopen_cash("],
    ),
    HookSpec(
        hook_id="execution.preopen_reject_orders",
        module="rebuild_from_archive.compat.execution",
        symbol="PREOPEN_REJECT_ORDERS",
        data_obj=PREOPEN_REJECT_ORDERS,
        affected_fields=["preopen_order_acceptance"],
        behavior="Reject whole pre-open orders for explicit date/code pairs.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="This is only meaningful for replaying specific historical JoinQuant refusals.",
        evidence="engine/core.py calls compat.should_reject_preopen_order inside _should_reject_jq_preopen_order.",
        affects_selection=False,
        affects_state=False,
        affects_order=True,
        affects_fill=False,
        affects_nav=False,
        target_owner="jq_archive",
        wave="L2",
        direct_effect_scope=["order_presence"],
        downstream_risk="strategy_path",
        empty_config=True,
        handoff_requirement="Keep only with the archived JQ execution profile.",
        disable_requirement="Can be disabled with JQ parity hooks; impacts order presence but not upstream candidate logic.",
        delete_requirement="Delete after dropping archived JoinQuant pre-open order replay support.",
        acceptance_test="Inventory scan only; current set is empty so retirement risk is low.",
        status="archive_candidate",
        call_site_patterns=["should_reject_preopen_order("],
    ),
    HookSpec(
        hook_id="execution.preopen_drop_first_duplicate",
        module="rebuild_from_archive.compat.execution",
        symbol="PREOPEN_DROP_FIRST_DUPLICATE",
        data_obj=PREOPEN_DROP_FIRST_DUPLICATE,
        affected_fields=["pending_orders"],
        behavior="Drop the first duplicate pre-open pending order on recorded dates to match JoinQuant queue behavior.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="This duplicates a platform queue quirk, not a stable project rule.",
        evidence="engine/core.py calls compat.should_drop_first_preopen_duplicate inside _apply_jq_preopen_duplicate_order_anomaly.",
        affects_selection=False,
        affects_state=False,
        affects_order=True,
        affects_fill=False,
        affects_nav=False,
        target_owner="jq_archive",
        wave="L2",
        direct_effect_scope=["order_presence"],
        downstream_risk="strategy_path",
        handoff_requirement="Keep only in the JQ replay profile; local-native should use native duplicate-order handling.",
        disable_requirement="Can be disabled with only order-path effects once JQ parity is no longer required.",
        delete_requirement="Delete after archived JoinQuant duplicate-order replay is retired.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2021 preopen duplicate check",
        status="archive_candidate",
        call_site_patterns=["should_drop_first_preopen_duplicate("],
    ),
    HookSpec(
        hook_id="execution.execution_price_anomalies",
        module="rebuild_from_archive.compat.execution",
        symbol="EXECUTION_PRICE_ANOMALIES",
        data_obj=EXECUTION_PRICE_ANOMALIES,
        affected_fields=["trade_price"],
        behavior="Force execution prices for specific date/time/code/side combinations on the parity path.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="These are historical fill answers, not a general-purpose matcher rule.",
        evidence="engine/core.py queries get_execution_price_override inside _apply_jq_execution_price_anomaly during order matching.",
        affects_selection=False,
        affects_state=False,
        affects_order=False,
        affects_fill=True,
        affects_nav=True,
        target_owner="jq_archive",
        wave="L1A",
        direct_effect_scope=["price"],
        downstream_risk="cash_path",
        handoff_requirement="Archive with the JQ replay execution profile; do not upstream to local-native matching.",
        disable_requirement="Good first-wave disable candidate for local-native if fill-price drift is acceptable.",
        delete_requirement="Delete after JoinQuant execution-price parity is no longer maintained.",
        acceptance_test="tests/test_compat_entrypoints.py::test_minute_and_execution_overrides",
        status="archive_candidate",
        call_site_patterns=["get_execution_price_override("],
    ),
    HookSpec(
        hook_id="execution.order_amount_anomalies",
        module="rebuild_from_archive.compat.execution",
        symbol="ORDER_AMOUNT_ANOMALIES",
        data_obj=ORDER_AMOUNT_ANOMALIES,
        affected_fields=["order_amount"],
        behavior="Force order quantities for specific pre-open or open events on the mother replay path.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="These are historical mother-path answers, not reusable sizing logic.",
        evidence="engine/core.py applies get_order_amount_override inside _apply_jq_order_amount_anomaly before creating orders.",
        affects_selection=False,
        affects_state=False,
        affects_order=True,
        affects_fill=True,
        affects_nav=True,
        target_owner="jq_archive",
        wave="L1B",
        direct_effect_scope=["size"],
        downstream_risk="position_path",
        handoff_requirement="Keep only with the archived mother/JQ parity profile.",
        disable_requirement="Can be disabled in local-native mode; expect trade-size and NAV drift but not upstream candidate changes.",
        delete_requirement="Delete when the project stops preserving mother-path quantity parity.",
        acceptance_test="tests/test_compat_entrypoints.py::test_order_amount_sequence_config_and_fill_override",
        status="archive_candidate",
        call_site_patterns=["get_order_amount_override("],
    ),
    HookSpec(
        hook_id="execution.fill_amount_anomalies",
        module="rebuild_from_archive.compat.execution",
        symbol="FILL_AMOUNT_ANOMALIES",
        data_obj=FILL_AMOUNT_ANOMALIES,
        affected_fields=["fill_amount"],
        behavior="Force fill share counts for specific orders when replaying archived fills.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="This is fill-answer replay, not a generic exchange or broker rule.",
        evidence="engine/core.py applies get_fill_amount_override inside _apply_jq_fill_amount_anomaly during matching.",
        affects_selection=False,
        affects_state=False,
        affects_order=False,
        affects_fill=True,
        affects_nav=True,
        target_owner="jq_archive",
        wave="L1B",
        direct_effect_scope=["size"],
        downstream_risk="position_path",
        handoff_requirement="Archive with other JQ-only fill answer hooks.",
        disable_requirement="Can be disabled with only fill and NAV consequences once parity mode is not required.",
        delete_requirement="Delete after archived fill-size parity support is retired.",
        acceptance_test="tests/test_compat_entrypoints.py::test_order_amount_sequence_config_and_fill_override",
        status="archive_candidate",
        call_site_patterns=["get_fill_amount_override("],
    ),
    HookSpec(
        hook_id="call_auction.empty_anomalies",
        module="rebuild_from_archive.compat.call_auction",
        symbol="CALL_AUCTION_EMPTY_ANOMALIES",
        data_obj=CALL_AUCTION_EMPTY_ANOMALIES,
        affected_fields=["call_auction_rows"],
        behavior="Remove specific call-auction rows entirely before candidate logic consumes them.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="The current evidence shows row suppression but does not yet prove whether the source is wrong or JoinQuant-only.",
        evidence="project_compat.apply_call_auction_overrides removes rows keyed by CALL_AUCTION_EMPTY_ANOMALIES and engine/data_api.py calls it in get_call_auction.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="investigation",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Need source-vs-reference row-level evidence before assigning to HData or JQ archive.",
        disable_requirement="Disable only after call-auction candidate behavior is accepted without these row deletions.",
        delete_requirement="Delete once the source owner is assigned and either repaired upstream or archived as JQ-only.",
        acceptance_test="tests/test_compat_entrypoints.py::test_call_auction_overrides_apply",
        status="investigation_pending",
        call_site_patterns=["apply_call_auction_overrides("],
    ),
    HookSpec(
        hook_id="call_auction.allow_only",
        module="rebuild_from_archive.compat.call_auction",
        symbol="CALL_AUCTION_ALLOW_ONLY",
        data_obj=CALL_AUCTION_ALLOW_ONLY,
        affected_fields=["call_auction_rows"],
        behavior="Restrict a day's auction dataset to an allow-list of codes before ranking.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="The allow-list may reflect source contamination or a JQ extract quirk; ownership is not yet proven.",
        evidence="project_compat.apply_call_auction_overrides enforces CALL_AUCTION_ALLOW_ONLY before candidate ranking reads the frame.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="investigation",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Need per-day upstream data evidence to decide whether this belongs in HData or the JQ archive bucket.",
        disable_requirement="Disable only after accepting candidate drift for the affected dates in non-parity mode.",
        delete_requirement="Delete after root-cause assignment and either source repair or archival.",
        acceptance_test="tests/test_compat_entrypoints.py::test_call_auction_overrides_apply",
        status="investigation_pending",
        call_site_patterns=["apply_call_auction_overrides("],
    ),
    HookSpec(
        hook_id="call_auction.depth_overrides",
        module="rebuild_from_archive.compat.call_auction",
        symbol="CALL_AUCTION_DEPTH_OVERRIDES",
        data_obj=CALL_AUCTION_DEPTH_OVERRIDES,
        affected_fields=["a1_v"],
        behavior="Patch specific call-auction depth fields before candidate ranking.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="These look like source-field corrections, but current evidence is not strong enough to assign them permanently to HData.",
        evidence="project_compat.apply_call_auction_overrides patches the requested columns, and tests assert the 2020-09-03 override.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="investigation",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Need raw call-auction depth evidence and a source owner before handoff.",
        disable_requirement="Disable only after proving candidate ranking is acceptable without the patched depth values.",
        delete_requirement="Delete after source ownership is resolved and the patch is either repaired upstream or archived.",
        acceptance_test="tests/test_compat_entrypoints.py::test_call_auction_overrides_apply",
        status="investigation_pending",
        call_site_patterns=["apply_call_auction_overrides("],
    ),
    HookSpec(
        hook_id="security_metadata.start_date_overrides",
        module="rebuild_from_archive.compat.security_metadata",
        symbol="SECURITY_START_DATE_OVERRIDES",
        data_obj=SECURITY_START_DATE_OVERRIDES,
        affected_fields=["start_date"],
        behavior="Replace listing dates for specific securities before IPO-age filters run.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="Listing-date truth belongs to the data layer, but the discrepancy may reflect JoinQuant listing-date conventions rather than HData errors. Pending independent verification.",
        evidence="engine/data_api.py applies get_security_start_date_override while building _stock_basic for get_all_securities().",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="hdata_candidate",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="HData needs a corrected listing-date source or overlay for these securities.",
        disable_requirement="Disable only after stock_basic or its replacement publishes correct PIT listing dates.",
        delete_requirement="Delete after HData ships corrected listing dates and all IPO-age filters read them directly.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2020 IPO override checks",
        status="investigation_pending",
        call_site_patterns=["get_security_start_date_override("],
    ),
    HookSpec(
        hook_id="security_metadata.non_st_name_windows",
        module="rebuild_from_archive.compat.security_metadata",
        symbol="NON_ST_NAME_WINDOWS",
        data_obj=NON_ST_NAME_WINDOWS,
        affected_fields=["display_name"],
        behavior="Strip future ST or delisting markers from PIT display names inside explicit date windows.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="Historical security-name state is source metadata, but the divergence may stem from JoinQuant name-history conventions vs local data PIT snapshots. Pending independent verification.",
        evidence="project_compat.apply_security_name_overrides applies NON_ST_NAME_WINDOWS after reading daily ST state and before strategy filters consume display_name.",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="hdata_candidate",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="HData needs PIT name history or equivalent metadata to eliminate these date-window strips.",
        disable_requirement="Disable only after display_name is PIT-correct for affected windows.",
        delete_requirement="Delete after PIT name history is available and strategy filters no longer need compat name surgery.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2021 ST name window check",
        status="investigation_pending",
        call_site_patterns=["apply_security_name_overrides("],
    ),
    HookSpec(
        hook_id="security_metadata.special_display_name_rules",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.apply_security_name_overrides",
        data_obj={"special_codes": ["001270.XSHE", "600856.XSHG"], "dates": ["2020-05-07", "2022-04-18"]},
        affected_fields=["display_name"],
        behavior="Apply extra security-name compatibility rules beyond the window table, including explicit special-code branches.",
        semantic_type="unknown",
        disposition="investigate",
        reason="The special-case branches mix PIT naming concerns with hardcoded stock-specific logic and need decomposition before ownership can be assigned.",
        evidence="project_compat.apply_security_name_overrides contains special handling for 001270.XSHE and 600856.XSHG outside NON_ST_NAME_WINDOWS.",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="investigation",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Split general PIT name logic from single-stock legacy rules and re-evaluate ownership.",
        disable_requirement="Disable only after each remaining special-case is either absorbed by PIT metadata or explicitly archived as JQ-only.",
        delete_requirement="Delete after the method no longer needs stock-specific name branches.",
        acceptance_test="Inventory scan and manual review of project_compat.apply_security_name_overrides branches",
        status="investigation_pending",
        call_site_patterns=["apply_security_name_overrides("],
        manual_dates=["2020-05-07", "2022-04-18"],
        manual_codes=["001270.XSHE", "600856.XSHG"],
        count_override=2,
    ),
    HookSpec(
        hook_id="security_metadata.adjust_extras_is_st",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.adjust_extras_is_st",
        data_obj={"dates": ["2020-05-07", "2024-05-01", "2024-06-03"], "codes": ["600856.XSHG"]},
        affected_fields=["is_st", "display_name", "end_date"],
        behavior="Override is_st results using PIT name and end-date heuristics for specific windows and codes.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="ST state and delisting-state truth should come from source metadata, but the divergence may reflect JoinQuant ST classification conventions rather than HData errors. Pending verification.",
        evidence="engine/data_api.py calls compat.adjust_extras_is_st from get_extras('is_st', ...), and project_compat.py embeds date windows and name/end_date heuristics.",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="hdata_candidate",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="HData needs PIT ST status and delisting-state history that match the project's required query dates.",
        disable_requirement="Disable only after get_extras('is_st') reads corrected PIT ST state directly.",
        delete_requirement="Delete after ST state is natively correct and the project no longer patches it post-query.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2024 ST rule check",
        status="investigation_pending",
        call_site_patterns=["adjust_extras_is_st("],
        manual_dates=["2020-05-07", "2024-05-01", "2024-06-03"],
        manual_codes=["600856.XSHG"],
        count_override=3,
    ),
    HookSpec(
        hook_id="security_metadata.billboard_row_filters",
        module="rebuild_from_archive.compat.security_metadata",
        symbol="BILLBOARD_ROW_FILTERS",
        data_obj=BILLBOARD_ROW_FILTERS,
        affected_fields=["billboard_rows"],
        behavior="Drop specific billboard rows before strategy-side candidate logic reads them.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="This looks like data cleanup, but the current evidence does not yet prove whether the underlying billboard source or JoinQuant export is wrong.",
        evidence="engine/data_api.py calls compat.filter_billboard_rows in get_billboard_list, and project_compat.filter_billboard_rows keys off BILLBOARD_ROW_FILTERS.",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="investigation",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="strategy_path",
        handoff_requirement="Need row-level upstream billboard evidence before assigning to HData or archive-only replay.",
        disable_requirement="Disable only after validating candidate behavior on affected dates without the row drop.",
        delete_requirement="Delete after root cause is assigned and addressed by the right owner.",
        acceptance_test="tools/run_counterfactual_2024_000506_billboard_filter.py demonstrates nearby workflow but not full retirement criteria.",
        status="investigation_pending",
        call_site_patterns=["filter_billboard_rows("],
    ),
    HookSpec(
        hook_id="instrument_fallbacks.price_fallbacks",
        module="rebuild_from_archive.compat.instrument_fallbacks",
        symbol="INSTRUMENT_PRICE_FALLBACKS",
        data_obj=INSTRUMENT_PRICE_FALLBACKS,
        affected_fields=["open", "close", "high", "low", "volume", "money"],
        behavior="Serve synthetic daily prices for instruments missing or unusable in the local data path.",
        semantic_type="data_correction",
        disposition="investigate",
        reason="Instrument price history should come from the data layer, but the absence may reflect data-coverage gaps rather than HData errors. Pending verification.",
        evidence="engine/data_api.py short-circuits get_price via compat.get_instrument_price_fallback before touching local price tables.",
        affects_selection=True,
        affects_state=False,
        affects_order=True,
        affects_fill=False,
        affects_nav=True,
        target_owner="hdata_candidate",
        wave=None,
        direct_effect_scope=["data_shape"],
        downstream_risk="position_path",
        handoff_requirement="HData needs complete and trustworthy history for the fallback instruments or an explicit supported-source overlay.",
        disable_requirement="Disable only after local data can serve these instruments directly without synthetic rows.",
        delete_requirement="Delete after HData publishes native coverage and no call path reaches get_instrument_price_fallback.",
        acceptance_test="tests/test_compat_entrypoints.py::test_strategy_state_override_and_instrument_fallback",
        status="investigation_pending",
        call_site_patterns=["get_instrument_price_fallback("],
    ),
    HookSpec(
        hook_id="instrument_fallbacks.zero_fee_overrides",
        module="rebuild_from_archive.compat.instrument_fallbacks",
        symbol="ZERO_FEE_OVERRIDES",
        data_obj=ZERO_FEE_OVERRIDES,
        affected_fields=["commission", "tax"],
        behavior="Treat specific instruments as zero-fee in the engine fee path.",
        semantic_type="market_rule",
        disposition="move_to_local_quant",
        reason="Fee classification belongs in the generic instrument/fee model, not in project compat constants.",
        evidence="engine/core.py calls compat.has_zero_fee_override from buy/sell fee estimation and realized fee logic.",
        affects_selection=False,
        affects_state=False,
        affects_order=False,
        affects_fill=True,
        affects_nav=True,
        target_owner="local_quant",
        wave=None,
        direct_effect_scope=["fee"],
        downstream_risk="nav_only",
        handoff_requirement="local_quant needs instrument-class-aware fee configuration that covers these cases natively.",
        disable_requirement="Disable only after fee policy is modeled in local_quant by instrument type or explicit configuration.",
        delete_requirement="Delete after engine/core.py no longer checks compat.has_zero_fee_override and fee policy is generic.",
        acceptance_test="tests/test_compat_entrypoints.py::test_strategy_state_override_and_instrument_fallback",
        status="handoff_pending",
        call_site_patterns=["has_zero_fee_override("],
    ),
    HookSpec(
        hook_id="strategy_state.fb_state_overrides",
        module="rebuild_from_archive.compat.strategy_state",
        symbol="FB_STATE_OVERRIDES",
        data_obj=FB_STATE_OVERRIDES,
        affected_fields=["first_board_perf", "fb_pct", "fb_perf_history"],
        behavior="Force first-board performance state snapshots on specific dates after fb-state computation.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="These dates preserve historical JoinQuant state answers and do not represent a reusable project rule.",
        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_fb_state', ...) and project_compat.apply_strategy_state_override applies FB_STATE_OVERRIDES.",
        affects_selection=True,
        affects_state=True,
        affects_order=True,
        affects_fill=False,
        affects_nav=False,
        target_owner="jq_archive",
        wave="L3",
        direct_effect_scope=["state"],
        downstream_risk="strategy_path",
        handoff_requirement="Keep only with the archived JQ replay profile; local-native state should derive from native computations.",
        disable_requirement="Do not disable until local-native mode explicitly accepts candidate/state divergence on these dates.",
        delete_requirement="Delete after the project stops supporting JoinQuant state-snapshot replay.",
        acceptance_test="tests/test_compat_entrypoints.py::test_strategy_state_override_and_instrument_fallback",
        status="archive_candidate",
        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],
    ),
    HookSpec(
        hook_id="strategy_state.v227_shock_overrides",
        module="rebuild_from_archive.compat.strategy_state",
        symbol="V227_SHOCK_OVERRIDES",
        data_obj=V227_SHOCK_OVERRIDES,
        affected_fields=["v227_shock_cooldown"],
        behavior="Force v227 shock cooldown state on a recorded retreat day after the strategy computes shock state.",
        semantic_type="jq_platform_behavior",
        disposition="archive_jq_only",
        reason="This is a historical parity answer for one state transition, not a general strategy definition.",
        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_v227_shock', ...) and project_compat.apply_strategy_state_override applies V227_SHOCK_OVERRIDES.",
        affects_selection=True,
        affects_state=True,
        affects_order=True,
        affects_fill=False,
        affects_nav=False,
        target_owner="jq_archive",
        wave="L3",
        direct_effect_scope=["state"],
        downstream_risk="strategy_path",
        handoff_requirement="Keep only for archived JQ replay; local-native should use native state transitions.",
        disable_requirement="Do not disable until the project accepts branch-trigger drift for the affected date in local-native mode.",
        delete_requirement="Delete after JQ shock-state replay is retired.",
        acceptance_test="tools/hook_migration_acceptance.py targeted 2023 v227 shock check",
        status="archive_candidate",
        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],
    ),
    HookSpec(
        hook_id="project_feature.first_seal_loader",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.load_first_seal_year",
        data_obj={"feature": "first_seal_time"},
        affected_fields=["first_limit_hit_time", "project_cache/features/first_seal_time"],
        behavior="Load and filter project first-seal cache rows before runtime sealing-point lookups use them.",
        semantic_type="project_infrastructure",
        disposition="retain_in_project",
        reason="This is a project feature-cache integration point, not a generic market rule or external data fact.",
        evidence="engine/data_api.py delegates _load_project_first_seal_year to compat.load_first_seal_year and get_batch_sealing_points consumes the result.",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="strategy_path",
        handoff_requirement="Retain while project-specific feature caches remain part of the strategy runtime.",
        disable_requirement="Disable only if first-seal cache loading is removed or replaced by a different project feature pipeline.",
        delete_requirement="Delete after the project no longer uses first_seal_time cache lookups in runtime or has moved them into a different project-owned service.",
        acceptance_test="Inventory scan: verifies first_seal_time cache is loaded through compat integration point",
        status="retain",
        call_site_patterns=["load_first_seal_year(", "get_batch_sealing_points("],
        count_override=1,
    ),
    HookSpec(
        hook_id="project_feature.board_snapshot_accessor",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.get_project_board_snapshot",
        data_obj={"feature": "board_snapshot"},
        affected_fields=["board_snapshot", "board_count", "is_first_board"],
        behavior="Expose project board-snapshot cache rows to strategy code as a project-specific fast path.",
        semantic_type="project_infrastructure",
        disposition="retain_in_project",
        reason="Board snapshot is a project-derived feature accessor, not alpha logic. It belongs to the project infrastructure layer.",
        evidence="母版-20260506-Clone.py reads get_project_board_snapshot(context.previous_date) for board scans; engine/data_api.py delegates through compat.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="strategy_path",
        handoff_requirement="Retain while the strategy depends on board_snapshot cache acceleration and project-specific data-quality policy.",
        disable_requirement="Disable only if strategy switches to a different project-owned feature source or recomputes the logic natively.",
        delete_requirement="Delete after project runtime no longer depends on board_snapshot compat exposure.",
        acceptance_test="Inventory scan: verifies board_snapshot compat is used by strategy code on main path",
        status="retain",
        call_site_patterns=["get_project_board_snapshot("],
        count_override=1,
    ),
    HookSpec(
        hook_id="project_feature.master_prepare_index_accessor",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.get_project_master_prepare_index",
        data_obj={"feature": "master_prepare_index"},
        affected_fields=["master_prepare_index"],
        behavior="Expose the project's master_prepare_index cache to runtime callers through compat.",
        semantic_type="project_infrastructure",
        disposition="investigate",
        reason="Main path has no direct strategy consumer. If only definition and forwarding exist without strategy usage, it should enter unused cleanup candidate.",
        evidence="engine/data_api.py delegates get_project_master_prepare_index through compat; no direct strategy consumer is currently present on the main path.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="strategy_path",
        handoff_requirement="Confirm if there are real runtime consumers. If only definition and forwarding without strategy usage, enter unused cleanup candidate.",
        disable_requirement="Disable only if the project removes this cache or rewires the consumer path.",
        delete_requirement="Delete after there are no project callers and no fast-path cache exposure for master_prepare_index.",
        acceptance_test="Inventory scan should flag that current direct runtime call sites are limited.",
        status="investigation_pending",
        call_site_patterns=["get_project_master_prepare_index("],
        count_override=1,
    ),
    HookSpec(
        hook_id="project_feature.auction_yiqian_prepare_accessor",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.get_project_auction_yiqian_prepare",
        data_obj={"feature": "auction_yiqian_prepare"},
        affected_fields=["auction_yiqian_prepare", "left_ok"],
        behavior="Expose cached auction_yiqian_prepare rows to strategy code and patch left-pressure checks onto them.",
        semantic_type="project_infrastructure",
        disposition="retain_in_project",
        reason="This accessor is specific to the project's derived candidate-preparation feature set, not strategy alpha logic.",
        evidence="母版-20260506-Clone.py reads get_project_auction_yiqian_prepare(context.current_dt), and project_compat.get_project_auction_yiqian_prepare also runs project-specific left-pressure logic.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="strategy_path",
        handoff_requirement="Retain while auction_yiqian_prepare remains part of the project feature graph.",
        disable_requirement="Disable only if the project removes this cache path or replaces it with a different project-owned feature service.",
        delete_requirement="Delete after no runtime caller depends on auction_yiqian_prepare compat exposure.",
        acceptance_test="Inventory scan: verifies auction_yiqian_prepare compat is consumed by strategy code",
        status="retain",
        call_site_patterns=["get_project_auction_yiqian_prepare("],
        count_override=1,
    ),
    HookSpec(
        hook_id="project_feature.call_auction_day_loader",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.load_project_call_auction_day",
        data_obj={"feature": "call_auction_by_date"},
        affected_fields=["call_auction_by_date"],
        behavior="Swap the generic call-auction year read for the project's by-date cache when available.",
        semantic_type="project_infrastructure",
        disposition="retain_in_project",
        reason="This is a project cache integration point for a derived feature layout, not strategy alpha logic.",
        evidence="engine/data_api.py calls compat.load_project_call_auction_day from _get_call_auction_day before falling back to raw 1d_feature/call_auction.",
        affects_selection=True,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="strategy_path",
        handoff_requirement="Retain while the project prefers its by-date call-auction cache layout.",
        disable_requirement="Disable only if runtime stops consulting the project call_auction_by_date cache.",
        delete_requirement="Delete after the project no longer needs this alternate loader path.",
        acceptance_test="Inventory scan: verifies call_auction_by_date cache loader is consumed via compat",
        status="retain",
        call_site_patterns=["load_project_call_auction_day("],
        count_override=1,
    ),
    HookSpec(
        hook_id="project_feature.strategy_namespace_bridge",
        module="rebuild_from_archive.project_compat",
        symbol="EmotionGateJQCompat.namespace_entries/apply_project_strategy_compat",
        data_obj={"entrypoint": "apply_project_strategy_compat"},
        affected_fields=["strategy_state"],
        behavior="Inject project-owned compat entrypoints into the strategy namespace, including the strategy-state bridge.",
        semantic_type="project_infrastructure",
        disposition="retain_in_project",
        reason="Namespace wiring is project infrastructure that allows strategy code to call project-owned compatibility services. The bridge itself is infrastructure; JQ history overrides called through it are archive_jq_only.",
        evidence="Engine.__init__ merges compat.namespace_entries(self), and 母版-20260506-Clone.py calls apply_project_strategy_compat(...) at fixed stages.",
        affects_selection=True,
        affects_state=True,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="strategy_path",
        handoff_requirement="Retain until project-owned feature and state hooks are redesigned or removed.",
        disable_requirement="Disable only after the strategy no longer expects these injected entrypoints.",
        delete_requirement="Delete after project compat entrypoints are removed or replaced by a new project extension surface.",
        acceptance_test="Inventory scan plus tests/test_compat_entrypoints.py state override checks",
        status="retain",
        call_site_patterns=["namespace_entries(", "apply_project_strategy_compat("],
        count_override=1,
    ),
    HookSpec(
        hook_id="engine.checkpoint_resume_hook",
        module="rebuild_from_archive.engine.core",
        symbol="Engine.set_resume_state/_apply_resume_state",
        data_obj={"hook": "resume_state"},
        affected_fields=["portfolio", "g_data", "order_id_counter"],
        behavior="Restore project checkpoint state into the engine before the run loop starts.",
        semantic_type="project_infrastructure",
        disposition="retain_in_project",
        reason="This is a project warm-start/checkpoint integration hook, not a JQ historical fact bundle or strategy alpha logic. May be migrated to shared engine extension API in the future.",
        evidence="engine/core.py marks the resume hook with EMOTION_GATE_COMPAT_HOOK comments and tools/run_counterfactual_2024_000506_billboard_filter.py uses engine.set_resume_state(...).",
        affects_selection=True,
        affects_state=True,
        affects_order=True,
        affects_fill=False,
        affects_nav=True,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="strategy_path",
        handoff_requirement="Retain until checkpoint responsibilities are redesigned outside the generic engine or explicitly migrated to a shared extension API.",
        disable_requirement="Disable only after all checkpoint-based workflows are removed or replaced.",
        delete_requirement="Delete after no workflow uses set_resume_state and checkpoint restore is moved elsewhere.",
        acceptance_test="Inventory scan of EMOTION_GATE_COMPAT_HOOK sites and manual workflow reference in tools/run_counterfactual_2024_000506_billboard_filter.py",
        status="retain",
        call_site_patterns=["set_resume_state(", "_apply_resume_state(", "EMOTION_GATE_COMPAT_HOOK"],
        count_override=1,
    ),
    HookSpec(
        hook_id="legacy.public_data_api_shim",
        module="rebuild_from_archive.data_api",
        symbol="rebuild_from_archive.data_api.DataAPI",
        data_obj={"legacy_entrypoint": "rebuild_from_archive/data_api.py"},
        affected_fields=["public_import_path"],
        behavior="Re-export the archived legacy DataAPI implementation from the old public import path.",
        semantic_type="unknown",
        disposition="investigate",
        reason="This is a compatibility entrypoint for legacy/manual callers, but its external dependency surface is not fully inventoried yet.",
        evidence="rebuild_from_archive/data_api.py dynamically loads rebuild_from_archive/legacy/data_api_legacy.py; legacy/README.md lists only the public shim as a known in-repo caller.",
        affects_selection=False,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave=None,
        direct_effect_scope=["infrastructure"],
        downstream_risk="none",
        handoff_requirement="Need an explicit caller audit across manual workflows before deleting the public shim.",
        disable_requirement="Disable only after external/manual callers are confirmed gone or migrated to engine/data_api.py.",
        delete_requirement="Delete after the public import path is unused and legacy workflows have been redirected.",
        acceptance_test="Inventory scan should mark this as having no active main-path runtime call sites inside the repo.",
        status="investigation_pending",
        call_site_patterns=[
            "from rebuild_from_archive.data_api",
            "import rebuild_from_archive.data_api",
            "rebuild_from_archive/data_api.py",
        ],
        count_override=1,
    ),
    HookSpec(
        hook_id="legacy.temporary_fallbacks_shim",
        module="rebuild_from_archive.engine.temporary_fallbacks",
        symbol="get_price_fallback/has_zero_fee_fallback",
        data_obj={"shim": "temporary_fallbacks"},
        affected_fields=["fallback_import_path"],
        behavior="Closed shim that intentionally returns no fallback so old imports do not introduce a second fact source.",
        semantic_type="unknown",
        disposition="investigate",
        reason="This module exists only to absorb deprecated imports from the old JQ parity path. It is a legacy cleanup item, not a strategy ablation variable.",
        evidence="rebuild_from_archive/engine/temporary_fallbacks.py documents itself as a non-operative shim and current repo scan shows no active runtime caller.",
        affects_selection=False,
        affects_state=False,
        affects_order=False,
        affects_fill=False,
        affects_nav=False,
        target_owner="emotion_gating_project",
        wave="cleanup-only",
        direct_effect_scope=["none"],
        downstream_risk="none",
        handoff_requirement="Keep only until any remaining legacy imports are proven gone; do not add new callers.",
        disable_requirement="Can be removed once import-path audit confirms there are no remaining users.",
        delete_requirement="Delete after repo and external workflow scans prove the shim is unused.",
        acceptance_test="Inventory scan should flag no active runtime call sites for temporary_fallbacks.",
        status="investigation_pending",
        call_site_patterns=[
            "from rebuild_from_archive.engine.temporary_fallbacks import",
            "import rebuild_from_archive.engine.temporary_fallbacks",
        ],
        count_override=1,
    ),
]


def build_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for spec in HOOK_SPECS:
        trigger_dates, trigger_codes = build_trigger_info(
            data_obj=spec.data_obj,
            manual_dates=spec.manual_dates,
            manual_codes=spec.manual_codes,
        )
        runtime_call_sites, secondary_refs = collect_call_sites(spec.call_site_patterns)
        def_cnt, fwd_cnt, cons_cnt = classify_call_lines(runtime_call_sites)
        record = {
            "hook_id": spec.hook_id,
            "module": spec.module,
            "symbol": spec.symbol,
            "call_sites": runtime_call_sites,
            "secondary_references": secondary_refs,
            "trigger_dates": trigger_dates,
            "trigger_codes": trigger_codes,
            "affected_fields": spec.affected_fields,
            "behavior": spec.behavior,
            "semantic_type": spec.semantic_type,
            "disposition": spec.disposition,
            "reason": spec.reason,
            "evidence": spec.evidence,
            "affects_selection": spec.affects_selection,
            "affects_state": spec.affects_state,
            "affects_order": spec.affects_order,
            "affects_fill": spec.affects_fill,
            "affects_nav": spec.affects_nav,
            "target_owner": spec.target_owner,
            "handoff_requirement": spec.handoff_requirement,
            "disable_requirement": spec.disable_requirement,
            "delete_requirement": spec.delete_requirement,
            "acceptance_test": spec.acceptance_test,
            "status": spec.status,
            "entry_count": spec.count_override if spec.count_override is not None else count_items(spec.data_obj),
            "year_tags": years_from_dates(trigger_dates),
            "runtime_callsite_count": len(runtime_call_sites),
            "secondary_reference_count": len(secondary_refs),
            "unused_runtime": len(runtime_call_sites) == 0,
            "wave": spec.wave,
            "direct_effect_scope": spec.direct_effect_scope or ["unknown"],
            "downstream_risk": spec.downstream_risk or "unknown",
            "empty_config": spec.empty_config,
            "definition_count": def_cnt,
            "forwarder_count": fwd_cnt,
            "consumer_count": cons_cnt,
            "external_evidence_ref": spec.external_evidence_ref,
            "external_evidence_status": spec.external_evidence_status,
        }
        inventory.append(record)
    return inventory


def summarize_inventory(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    def count_by(field: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in inventory:
            key = str(row[field])
            out[key] = out.get(key, 0) + 1
        return dict(sorted(out.items()))

    years: dict[str, int] = {}
    codes: dict[str, int] = {}
    for row in inventory:
        for year in row["year_tags"]:
            key = str(year)
            years[key] = years.get(key, 0) + 1
        for code in row["trigger_codes"]:
            codes[code] = codes.get(code, 0) + 1

    only_nav = 0
    for row in inventory:
        if row["affects_nav"] and not row["affects_selection"] and not row["affects_state"] and not row["affects_order"]:
            only_nav += 1

    unclassified = sum(1 for row in inventory if row["semantic_type"] == "unknown" or row["disposition"] == "investigate")
    no_runtime = sum(1 for row in inventory if row["runtime_callsite_count"] == 0)

    return {
        "hook_total": len(inventory),
        "by_semantic_type": count_by("semantic_type"),
        "by_disposition": count_by("disposition"),
        "by_status": count_by("status"),
        "by_wave": {k: v for k, v in count_by("wave").items() if k != "None"},
        "by_target_owner": count_by("target_owner"),
        "by_year": dict(sorted(years.items(), key=lambda kv: kv[0])),
        "by_code": dict(sorted(codes.items())),
        "affects_selection_count": sum(1 for row in inventory if row["affects_selection"]),
        "affects_state_count": sum(1 for row in inventory if row["affects_state"]),
        "affects_order_count": sum(1 for row in inventory if row["affects_order"]),
        "affects_fill_count": sum(1 for row in inventory if row["affects_fill"]),
        "affects_nav_only_count": only_nav,
        "no_runtime_callsite_count": no_runtime,
        "investigation_pending_count": sum(1 for row in inventory if row["status"] == "investigation_pending"),
        "unable_to_classify_count": unclassified,
        "empty_config_count": sum(1 for row in inventory if row["empty_config"]),
        "zero_consumer_count": sum(1 for row in inventory if row["consumer_count"] == 0),
        "hdata_confirmed_count": 0,
        "hdata_verification_queue_count": sum(1 for row in inventory if row["target_owner"] == "hdata_candidate" or (row["target_owner"] == "investigation" and row["semantic_type"] in ("data_correction", "unknown"))),
        "project_logic_count": sum(1 for row in inventory if row["semantic_type"] == "project_logic"),
        "project_infrastructure_count": sum(1 for row in inventory if row["semantic_type"] == "project_infrastructure"),
    }


def filter_hooks(
    inventory: list[dict[str, Any]],
    *,
    semantic_type: str | None = None,
    disposition: str | None = None,
    status: str | None = None,
    wave: str | None = None,
) -> list[dict[str, Any]]:
    rows = inventory
    if semantic_type is not None:
        rows = [row for row in rows if row["semantic_type"] == semantic_type]
    if disposition is not None:
        rows = [row for row in rows if row["disposition"] == disposition]
    if status is not None:
        rows = [row for row in rows if row["status"] == status]
    if wave is not None:
        rows = [row for row in rows if row["wave"] == wave]
    return rows


def hook_line(row: dict[str, Any]) -> str:
    return f"- `{row['hook_id']}`: `{row['symbol']}`"


def build_answers(inventory: list[dict[str, Any]]) -> dict[str, list[str]]:
    def ids(rows: list[dict[str, Any]]) -> list[str]:
        return [row["hook_id"] for row in rows]

    def dedupe(items: list[str]) -> list[str]:
        return sorted(dict.fromkeys(items))

    return {
        "general_market_rules": dedupe(ids(filter_hooks(inventory, semantic_type="market_rule"))),
        "hdata_verification_queue": dedupe(ids([row for row in inventory if row["target_owner"] == "hdata_candidate"])),
        "jq_history_replay_only": dedupe(ids(filter_hooks(inventory, semantic_type="jq_platform_behavior"))),
        "project_logic": dedupe(ids(filter_hooks(inventory, semantic_type="project_logic"))),
        "project_infrastructure": dedupe(ids(filter_hooks(inventory, semantic_type="project_infrastructure"))),
        "still_unknown": dedupe(
            ids(filter_hooks(inventory, semantic_type="unknown"))
            + ids([row for row in inventory if row["disposition"] == "investigate" and row["semantic_type"] not in ("data_correction", "unknown")])
        ),
        "wave_L1A": dedupe(ids(filter_hooks(inventory, wave="L1A"))),
        "wave_L1B": dedupe(ids(filter_hooks(inventory, wave="L1B"))),
        "wave_L2": dedupe(ids(filter_hooks(inventory, wave="L2"))),
        "wave_L3": dedupe(ids(filter_hooks(inventory, wave="L3"))),
        "wave_L4": dedupe(ids(filter_hooks(inventory, wave="L4"))),
        "cleanup_only": dedupe(ids(filter_hooks(inventory, wave="cleanup-only"))),
        "must_wait_for_local_quant": dedupe(ids([row for row in inventory if row["disposition"] == "move_to_local_quant"])),
        "must_wait_for_hdata_confirmed": dedupe([]),
        "zero_consumer_hooks": dedupe([row["hook_id"] for row in inventory if row["consumer_count"] == 0]),
        "empty_config_hooks": dedupe([row["hook_id"] for row in inventory if row["empty_config"]]),
        "external_evidence_refs": dedupe([row["hook_id"] for row in inventory if row["external_evidence_ref"]]),
    }


def render_inventory_markdown(inventory: list[dict[str, Any]], summary: dict[str, Any], answers: dict[str, list[str]]) -> str:
    lines: list[str] = []
    lines.append("# Hook Disposition Inventory")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Hook total: `{summary['hook_total']}`")
    lines.append(f"- By semantic_type: `{json.dumps(summary['by_semantic_type'], ensure_ascii=False)}`")
    lines.append(f"- By disposition: `{json.dumps(summary['by_disposition'], ensure_ascii=False)}`")
    lines.append(f"- By status: `{json.dumps(summary['by_status'], ensure_ascii=False)}`")
    lines.append(f"- By wave: `{json.dumps(summary['by_wave'], ensure_ascii=False)}`")
    lines.append(f"- By target_owner: `{json.dumps(summary['by_target_owner'], ensure_ascii=False)}`")
    lines.append(f"- By year: `{json.dumps(summary['by_year'], ensure_ascii=False)}`")
    lines.append(f"- Hooks touching selection: `{summary['affects_selection_count']}`")
    lines.append(f"- Hooks touching state: `{summary['affects_state_count']}`")
    lines.append(f"- Hooks touching order: `{summary['affects_order_count']}`")
    lines.append(f"- Hooks touching fill: `{summary['affects_fill_count']}`")
    lines.append(f"- Hooks affecting NAV only: `{summary['affects_nav_only_count']}`")
    lines.append(f"- Hooks with no active runtime call site: `{summary['no_runtime_callsite_count']}`")
    lines.append(f"- Hooks still requiring investigation: `{summary['investigation_pending_count']}`")
    lines.append(f"- Empty config entries: `{summary['empty_config_count']}`")
    lines.append(f"- Zero-consumer entries: `{summary['zero_consumer_count']}`")
    lines.append(f"- HData confirmed issues: `{summary['hdata_confirmed_count']}`")
    lines.append(f"- HData verification queue: `{summary['hdata_verification_queue_count']}`")
    lines.append(f"- project_logic: `{summary['project_logic_count']}`")
    lines.append(f"- project_infrastructure: `{summary['project_infrastructure_count']}`")
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    lines.append(f"1. **project_logic hooks**: {summary['project_logic_count']} — Current compat inventory contains **no true strategy alpha hooks**.")
    lines.append(f"2. **project_infrastructure hooks**: {summary['project_infrastructure_count']} — These are project cache access, namespace wiring, and checkpoint infrastructure.")
    lines.append(f"3. **HData confirmed**: {summary['hdata_confirmed_count']} — No hook has sufficient in-branch evidence to be classified as a confirmed HData error.")
    lines.append(f"4. **HData verification queue**: {summary['hdata_verification_queue_count']} — These need HData investigation before ownership assignment.")
    lines.append(f"5. **zero-consumer entries**: {summary['zero_consumer_count']} — Entries with no real strategy consumer needing investigation.")
    lines.append(f"6. **empty_config entries**: {summary['empty_config_count']} — Interface registrations with empty data that should not count as active behavior.")
    lines.append("")
    lines.append("## Questions")
    lines.append("")
    qa_map = [
        ("1. 哪些钩子属于通用市场规则？", "general_market_rules"),
        ("2. 哪些钩子是HData核实候选（待调查）？", "hdata_verification_queue"),
        ("3. 哪些钩子只是聚宽历史复刻？", "jq_history_replay_only"),
        ("4. 哪些钩子真正属于项目策略逻辑？", "project_logic"),
        ("5. 哪些钩子是项目基础设施？", "project_infrastructure"),
        ("6. 哪些钩子仍无法判断？", "still_unknown"),
        ("7. L1A（价格类）：可第一批关闭？", "wave_L1A"),
        ("8. L1B（数量类）：应第二批关闭？", "wave_L1B"),
        ("9. L2（订单存在性类）：应第三批关闭？", "wave_L2"),
        ("10. L3（状态历史答案类）：应第四批关闭？", "wave_L3"),
        ("11. L4（JQ数据形态类）：需本地数据确认后关闭？", "wave_L4"),
        ("12. 哪些不是消融项，只是遗留清理？", "cleanup_only"),
        ("13. 哪些没有真实消费者？", "zero_consumer_hooks"),
        ("14. 哪些配置为空？", "empty_config_hooks"),
        ("15. 哪些引用了外部未合并分支证据？", "external_evidence_refs"),
        ("16. 哪些必须等待local_quant？", "must_wait_for_local_quant"),
    ]
    for title, key in qa_map:
        lines.append(f"### {title}")
        rows = answers.get(key, [])
        if rows:
            for item in rows:
                lines.append(f"- `{item}`")
        else:
            lines.append("- none")
        lines.append("")

    lines.append("## Hook Table")
    lines.append("")
    lines.append("| hook_id | semantic_type | disposition | status | wave | years | codes | runtime call sites | consumer_count | target_owner |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for row in inventory:
        lines.append(
            f"| `{row['hook_id']}` | `{row['semantic_type']}` | `{row['disposition']}` | `{row['status']}` | "
            f"`{row['wave'] or '—'}` | `{','.join(str(y) for y in row['year_tags'])}` | `{','.join(row['trigger_codes'][:6])}` | "
            f"`{row['runtime_callsite_count']}` | `{row['consumer_count']}` | `{row['target_owner']}` |"
        )
    lines.append("")
    lines.append("## Detailed Hooks")
    lines.append("")
    for row in inventory:
        lines.append(f"### `{row['hook_id']}`")
        lines.append(f"- Module: `{row['module']}`")
        lines.append(f"- Symbol: `{row['symbol']}`")
        lines.append(f"- Behavior: {row['behavior']}")
        lines.append(f"- semantic_type / disposition / status: `{row['semantic_type']}` / `{row['disposition']}` / `{row['status']}`")
        lines.append(f"- Wave: `{row['wave'] or '—'}`")
        lines.append(f"- Affected fields: `{', '.join(row['affected_fields'])}`")
        lines.append(f"- Trigger dates: `{list_to_text(row['trigger_dates'])}`")
        lines.append(f"- Trigger codes: `{list_to_text(row['trigger_codes'])}`")
        lines.append(
            "- Effects: "
            f"selection={bool_text(row['affects_selection'])}, "
            f"state={bool_text(row['affects_state'])}, "
            f"order={bool_text(row['affects_order'])}, "
            f"fill={bool_text(row['affects_fill'])}, "
            f"nav={bool_text(row['affects_nav'])}"
        )
        lines.append(f"- direct_effect_scope: `{row['direct_effect_scope']}`")
        lines.append(f"- downstream_risk: `{row['downstream_risk']}`")
        lines.append(f"- empty_config: `{bool_text(row['empty_config'])}`")
        lines.append(f"- Reason: {row['reason']}")
        lines.append(f"- Evidence: {row['evidence']}")
        if row["external_evidence_ref"]:
            lines.append(f"- External evidence ref: `{row['external_evidence_ref']}`")
            lines.append(f"- External evidence status: `{row['external_evidence_status'] or 'unreviewed'}`")
        lines.append(f"- Runtime call sites: `{list_to_text(row['call_sites'])}`")
        if row["secondary_references"]:
            lines.append(f"- Secondary references: `{list_to_text(row['secondary_references'])}`")
        lines.append(f"- target_owner: `{row['target_owner']}`")
        lines.append(f"- handoff_requirement: {row['handoff_requirement']}")
        lines.append(f"- disable_requirement: {row['disable_requirement']}")
        lines.append(f"- delete_requirement: {row['delete_requirement']}")
        lines.append(f"- acceptance_test: {row['acceptance_test']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_handoff_markdown(title: str, intro: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", intro, ""]
    if not rows:
        lines.append("- none")
        return "\n".join(lines).strip() + "\n"
    for row in rows:
        lines.append(f"## `{row['hook_id']}`")
        lines.append(f"- symbol: `{row['symbol']}`")
        lines.append(f"- semantic_type / disposition: `{row['semantic_type']}` / `{row['disposition']}`")
        lines.append(f"- affects: selection={bool_text(row['affects_selection'])}, state={bool_text(row['affects_state'])}, order={bool_text(row['affects_order'])}, fill={bool_text(row['affects_fill'])}, nav={bool_text(row['affects_nav'])}")
        lines.append(f"- direct_effect_scope: `{row['direct_effect_scope']}`")
        lines.append(f"- downstream_risk: `{row['downstream_risk']}`")
        lines.append(f"- reason: {row['reason']}")
        lines.append(f"- evidence: {row['evidence']}")
        lines.append(f"- runtime call sites: `{list_to_text(row['call_sites'])}`")
        lines.append(f"- handoff requirement: {row['handoff_requirement']}")
        lines.append(f"- disable requirement: {row['disable_requirement']}")
        lines.append(f"- delete requirement: {row['delete_requirement']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_hdata_handoff(inventory: list[dict[str, Any]]) -> str:
    confirmed = [row for row in inventory if row["disposition"] == "move_to_hdata"]
    # HData verification queue: all hdata_candidate + data_correction items under investigation
    queue_core = [row for row in inventory if row["target_owner"] == "hdata_candidate"]
    queue_investigation = [
        row for row in inventory
        if row["target_owner"] == "investigation"
        and row["semantic_type"] in ("data_correction", "unknown")
        and row["hook_id"] not in {r["hook_id"] for r in queue_core}
    ]
    queue = queue_core + queue_investigation
    # Sort by hook_id for stability
    queue.sort(key=lambda r: r["hook_id"])

    lines = [
        "# HData Handoff",
        "",
        "## Confirmed HData Issues",
        "",
    ]
    if confirmed:
        for row in confirmed:
            lines.append(f"- `{row['hook_id']}`: {row['reason']}")
        lines.append("")
    else:
        lines.append("当前没有足够证据把任何钩子直接认定为HData已确认错误。")
        lines.append("")
        lines.append("所有疑似数据问题均需进一步调查才能确定归属。")
        lines.append("")

    lines.append("## HData Verification Queue")
    lines.append("")
    lines.append("以下项目需要HData核实后才能确定最终归属。每一行说明观察到什么、为什么怀疑HData、还有其他可能解释、需要什么证据。")
    lines.append("")

    if not queue:
        lines.append("- none")
        lines.append("")
        return "\n".join(lines).strip() + "\n"

    for row in queue:
        lines.append(f"### `{row['hook_id']}`")
        lines.append(f"- **观察到什么**: {row['behavior']}")
        lines.append(f"- **当前证据**: {row['evidence']}")
        lines.append(f"- **为什么怀疑HData**: {row['reason']}")
        lines.append(f"- **其他可能解释**: ")
        if "start_date" in row["hook_id"]:
            lines.append("  - 聚宽历史截面口径差异")
            lines.append("  - 公告日与生效日差异")
        elif "st" in row["hook_id"] or "name" in row["hook_id"]:
            lines.append("  - 名称/ST/退市状态口径差异")
            lines.append("  - 聚宽与本地复权口径差异")
            lines.append("  - 平台数据同步时间")
        elif "price_fallback" in row["hook_id"]:
            lines.append("  - 本地数据缺失（不是HData错误）")
            lines.append("  - 聚宽历史数据形态差异")
        else:
            lines.append("  - 聚宽历史数据形态差异")
            lines.append("  - 本地数据缺失")
            lines.append("  - 平台数据同步时间差异")
        lines.append(f"- **需要什么证据**: ")
        if "corrupted" in row["hook_id"]:
            lines.append("  - 确认2026-05-25起数据污染根因是HData上游问题")
            lines.append("  - 当前分支的外部线索（codex/data-quality-propagation-audit 未验收）不能作为已确认依据")
        else:
            lines.append("  - 逐笔对比聚宽与本地同一时间截面的原始数据")
            lines.append("  - 确认差异来源（口径 vs 错误）")
        lines.append(f"- **确认后如何修复**: HData修复数据源或发布字段级质量标记")
        lines.append(f"- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_local_quant_handoff(inventory: list[dict[str, Any]]) -> str:
    rows = [row for row in inventory if row["disposition"] == "move_to_local_quant"]
    lines = [
        "# Local Quant Handoff",
        "",
        "以下钩子描述的是通用市场、账户或费用行为，应迁移到 local_quant 作为平台通用能力。",
        "local_quant 不应为 emotion_gating 项目提供专用 boolean 开关，而应采用统一的账户结算政策、费用模型和证券类型分类。",
        "",
    ]

    if not rows:
        lines.append("- none")
        return "\n".join(lines).strip() + "\n"

    for row in rows:
        lines.append(f"## `{row['hook_id']}`")
        lines.append(f"- symbol: `{row['symbol']}`")
        lines.append(f"- semantic_type / disposition: `{row['semantic_type']}` / `{row['disposition']}`")
        lines.append(f"- affects: selection={bool_text(row['affects_selection'])}, state={bool_text(row['affects_state'])}, order={bool_text(row['affects_order'])}, fill={bool_text(row['affects_fill'])}, nav={bool_text(row['affects_nav'])}")
        lines.append(f"- direct_effect_scope: `{row['direct_effect_scope']}`")
        lines.append(f"- downstream_risk: `{row['downstream_risk']}`")
        lines.append(f"- reason: {row['reason']}")
        lines.append(f"- evidence: {row['evidence']}")
        lines.append(f"- runtime call sites: `{list_to_text(row['call_sites'])}`")

        if "sell_cash" in row["hook_id"]:
            lines.append("- **handoff requirement**: local_quant 应提供统一账户结算政策（卖出成交后的资金何时重新计入可用现金），而不是 emotion_gating 专用 boolean 开关。")
        elif "zero_fee" in row["hook_id"]:
            lines.append("- **handoff requirement**: local_quant 应按证券类型、交易品种和账户费用模型统一计算费用，而不是为 511880 单独保留项目 override。")
        else:
            lines.append(f"- handoff requirement: {row['handoff_requirement']}")

        lines.append(f"- disable requirement: {row['disable_requirement']}")
        lines.append(f"- delete requirement: {row['delete_requirement']}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_archive_plan_markdown(inventory: list[dict[str, Any]]) -> str:
    lines = [
        "# JQ Archive Plan",
        "",
        "These hooks exist to replay archived JoinQuant behavior and should not be carried into a future local-native baseline.",
        "",
        "## Ablation Waves",
        "",
        "### L1A — 价格类钩子（第一批关闭）",
        "",
    ]
    wave_l1a = [row for row in inventory if row["wave"] == "L1A"]
    for row in wave_l1a:
        lines.append(f"- `{row['hook_id']}`")
        lines.append(f"  - direct: {row['direct_effect_scope']}, downstream: {row['downstream_risk']}")
    lines.append("")

    lines.append("### L1B — 数量类钩子（第二批关闭）")
    lines.append("")
    wave_l1b = [row for row in inventory if row["wave"] == "L1B"]
    for row in wave_l1b:
        lines.append(f"- `{row['hook_id']}`")
        lines.append(f"  - direct: {row['direct_effect_scope']}, downstream: {row['downstream_risk']}")
    lines.append("")

    lines.append("### L2 — 订单存在性类钩子（第三批关闭）")
    lines.append("")
    wave_l2 = [row for row in inventory if row["wave"] == "L2"]
    for row in wave_l2:
        lines.append(f"- `{row['hook_id']}`")
        lines.append(f"  - direct: {row['direct_effect_scope']}, downstream: {row['downstream_risk']}")
    lines.append("")

    lines.append("### L3 — 状态历史答案类钩子（第四批关闭）")
    lines.append("")
    wave_l3 = [row for row in inventory if row["wave"] == "L3"]
    for row in wave_l3:
        lines.append(f"- `{row['hook_id']}`")
        lines.append(f"  - direct: {row['direct_effect_scope']}, downstream: {row['downstream_risk']}")
    lines.append("")

    lines.append("### L4 — JQ数据形态类钩子")
    lines.append("")
    lines.append("只有在本地原生模式明确接受本地数据形态后再关闭。")
    lines.append("")
    wave_l4 = [row for row in inventory if row["wave"] == "L4"]
    for row in wave_l4:
        lines.append(f"- `{row['hook_id']}`")
        lines.append(f"  - direct: {row['direct_effect_scope']}, downstream: {row['downstream_risk']}")
    lines.append("")

    lines.append("## 非消融项（Legacy Cleanup）")
    lines.append("")
    lines.append("以下不属于策略消融变量，只能在确认没有调用者后删除。")
    lines.append("")
    cleanup = [row for row in inventory if row["wave"] == "cleanup-only"]
    for row in cleanup:
        lines.append(f"- `{row['hook_id']}`: {row['reason']}")
    lines.append("")

    lines.append("## 所有 archive-only 钩子明细")
    lines.append("")
    archive_rows = [row for row in inventory if row["disposition"] == "archive_jq_only" or row["semantic_type"] == "jq_platform_behavior"]
    for row in archive_rows:
        lines.append(f"### `{row['hook_id']}`")
        lines.append(f"- 消融波次: `{row['wave'] or '—'}`")
        lines.append(f"- direct_effect_scope: `{row['direct_effect_scope']}`")
        lines.append(f"- downstream_risk: `{row['downstream_risk']}`")
        lines.append(f"- reason: {row['reason']}")
        lines.append(f"- affects selection/state/order/fill/nav: {bool_text(row['affects_selection'])}/{bool_text(row['affects_state'])}/{bool_text(row['affects_order'])}/{bool_text(row['affects_fill'])}/{bool_text(row['affects_nav'])}")
        lines.append(f"- empty_config: `{bool_text(row['empty_config'])}`")
        lines.append(f"- disable requirement: {row['disable_requirement']}")
        lines.append(f"- delete requirement: {row['delete_requirement']}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_csv(path: Path, inventory: list[dict[str, Any]]) -> None:
    columns = [
        "hook_id", "module", "symbol", "call_sites", "trigger_dates", "trigger_codes",
        "affected_fields", "behavior", "semantic_type", "disposition", "reason", "evidence",
        "affects_selection", "affects_state", "affects_order", "affects_fill", "affects_nav",
        "target_owner", "handoff_requirement", "disable_requirement", "delete_requirement",
        "acceptance_test", "status", "entry_count", "year_tags",
        "runtime_callsite_count", "secondary_reference_count", "unused_runtime",
        "wave", "direct_effect_scope", "downstream_risk", "empty_config",
        "definition_count", "forwarder_count", "consumer_count",
        "external_evidence_ref", "external_evidence_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in inventory:
            out = dict(row)
            for key in ("call_sites", "secondary_references", "trigger_dates", "trigger_codes", "affected_fields", "year_tags"):
                out[key] = list_to_text(out[key])
            out["direct_effect_scope"] = list_to_text(out.get("direct_effect_scope", []) or [])
            writer.writerow({k: out.get(k) for k in columns})


def write_outputs(out_dir: Path, inventory: list[dict[str, Any]], summary: dict[str, Any], answers: dict[str, list[str]]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "HOOK_INVENTORY.md"
    json_path = out_dir / "HOOK_INVENTORY.json"
    csv_path = out_dir / "HOOK_INVENTORY.csv"
    local_quant_path = out_dir / "LOCAL_QUANT_HANDOFF.md"
    hdata_path = out_dir / "HDATA_HANDOFF.md"
    archive_path = out_dir / "JQ_ARCHIVE_PLAN.md"

    json_payload = {
        "summary": summary,
        "answers": answers,
        "inventory": inventory,
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, inventory)
    md_path.write_text(render_inventory_markdown(inventory, summary, answers), encoding="utf-8")
    local_quant_path.write_text(render_local_quant_handoff(inventory), encoding="utf-8")
    hdata_path.write_text(render_hdata_handoff(inventory), encoding="utf-8")
    archive_path.write_text(render_archive_plan_markdown(inventory), encoding="utf-8")
    return {
        "markdown": str(md_path),
        "json": str(json_path),
        "csv": str(csv_path),
        "local_quant": str(local_quant_path),
        "hdata": str(hdata_path),
        "archive": str(archive_path),
    }


def audit_hook_disposition(out_dir: Path) -> dict[str, Any]:
    before = capture_hashes(PROTECTED_READONLY_PATHS)
    inventory = build_inventory()
    summary = summarize_inventory(inventory)
    answers = build_answers(inventory)
    artifacts = write_outputs(out_dir, inventory, summary, answers)
    after = capture_hashes(PROTECTED_READONLY_PATHS)
    if before != after:
        raise RuntimeError("Protected runtime files changed during hook disposition audit")
    return {
        "summary": summary,
        "artifacts": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "coordination" / "hook_disposition"),
        help="Directory where inventory artifacts will be written.",
    )
    args = parser.parse_args()
    result = audit_hook_disposition(Path(args.out_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
