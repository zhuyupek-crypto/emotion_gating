"""
Deprecated fallback shim.

Historical 511880 and zero-fee compatibility facts now live in
`rebuild_from_archive.compat.instrument_fallbacks` and are surfaced through
`EmotionGateJQCompat`. This module is intentionally kept as a non-operative
shim so old imports fail closed instead of introducing a second fact source.
"""


def get_price_fallback(security, start_date=None, end_date=None):
    return None


def has_zero_fee_fallback(security):
    return False
