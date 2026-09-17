"""Command-line entry point for the printer status worker."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="同步飞书表格中的打印机状态")
    parser.add_argument("--once", action="store_true", help="只执行一轮，用于首次测试")
    args = parser.parse_args()
    # 延迟加载 worker，使 `printer-status --help` 不要求先配置飞书凭证。
    from .worker import main as worker_main

    try:
        worker_main(once=args.once)
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
