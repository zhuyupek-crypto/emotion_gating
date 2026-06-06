import os
import sys
import time


ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "rebuild_from_archive")
sys.path.insert(0, WORK)

from project_preprocess import build_board_snapshot, build_call_auction_by_date, build_first_seal_time


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    start = time.time()
    board_path = build_board_snapshot(year)
    print(f"board_snapshot={board_path}", flush=True)
    seal_path = build_first_seal_time(year)
    print(f"first_seal_time={seal_path}", flush=True)
    auction_path = build_call_auction_by_date(year)
    print(f"call_auction_by_date={auction_path}", flush=True)
    print(f"completed in {time.time() - start:.2f}s", flush=True)


if __name__ == "__main__":
    main()
