"""Compatibility profile definitions for emotion-gate rebuild.

Each profile defines which hook groups are disabled.
Default profile (jq_parity) maintains full JoinQuant parity.
"""

JQ_PARITY = "jq_parity"
LOCAL_NATIVE_L1A = "local_native_l1a"
LOCAL_NATIVE_L1B = "local_native_l1b"

SUPPORTED_COMPAT_PROFILES = frozenset({
    JQ_PARITY,
    LOCAL_NATIVE_L1A,
    LOCAL_NATIVE_L1B,
})

PROFILE_DISABLED_HOOKS = {
    JQ_PARITY: frozenset(),
    LOCAL_NATIVE_L1A: frozenset({
        "market_data.minute_price_anomalies",
        "execution.execution_price_anomalies",
    }),
    LOCAL_NATIVE_L1B: frozenset({
        "market_data.minute_price_anomalies",
        "execution.execution_price_anomalies",
        "execution.order_amount_anomalies",
        "execution.fill_amount_anomalies",
    }),
}

