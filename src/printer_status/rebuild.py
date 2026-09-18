"""Rebuild utilization aggregates from raw SQLite samples."""

import argparse
import os

from dotenv import load_dotenv

from .state_store import StateStore


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="从原始采样重算打印机使用率")
    parser.add_argument("--db", default=os.getenv("STATE_DB_PATH", ".data/printer_status.db"))
    parser.add_argument(
        "--max-gap",
        type=float,
        default=float(os.getenv("MAX_COUNTED_GAP", "900")),
        help="两次采样允许计入统计的最大间隔（秒）",
    )
    args = parser.parse_args()
    store = StateStore(args.db, max_gap_seconds=args.max_gap)
    try:
        count = store.rebuild()
    finally:
        store.close()
    print(f"已重算 {count} 台打印机；原始 state_samples 未删除。")


if __name__ == "__main__":
    main()
