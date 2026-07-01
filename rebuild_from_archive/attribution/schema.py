"""Attribution schema constants for motherboard Phase 1B."""

SCHEMA_VERSION = "0.3"

BRANCH_VARIANTS = {
    "YJJ": "YJJ_PREPARED",
    "Scorpion": "SCORPION_PREPARED",
    "RZQ": "RZQ_PREPARED",
    "ZB": "ZB_PREPARED",
    "Auction": "AUCTION_PREPARED",
}

BUY_HANDLER_BRANCH = {
    "buy_v227_一进二": "YJJ",
    "buy_v227_天蝎座": "Scorpion",
    "buy_rzq": "RZQ",
    "buy_zb": "ZB",
    "buy_auction_yiqian": "Auction",
}

BRANCH_CANDIDATE_ATTR = {
    "YJJ": "yjj_candidates",
    "Scorpion": "bear_candidates",
    "RZQ": "rzq_candidates",
    "ZB": "zb_candidates",
    "Auction": "auction_yiqian_candidates",
}

BRANCH_ENABLE_ATTR = {
    "YJJ": "enable_v227",
    "Scorpion": "enable_v227",
    "RZQ": "enable_rzq",
    "ZB": "enable_zb",
    "Auction": "enable_auction_yiqian",
}

BRANCH_SLOT_ATTR = {
    "YJJ": "v227_slots",
    "Scorpion": "v227_slots",
    "RZQ": "rzq_slots",
    "ZB": "zb_slots",
    "Auction": "auction_yiqian_slots",
}

TERMINAL_STATES = [
    "FILLED",
    "BRANCH_FILTERED",
    "MOTHERBOARD_GATED_OUT",
    "ROUTED_OUT",
    "RANKED_OUT",
    "SLOT_BLOCKED",
    "CASH_BLOCKED",
    "POSITION_BLOCKED",
    "ORDER_NOT_CREATED",
    "ORDER_REJECTED",
    "DATA_INVALID",
    "NOT_EVALUATED_AFTER_STOP",
    "UNRESOLVED",
]
