"""Standalone printer connectivity probe; does not access Feishu."""

import argparse

from .adapters import PrinterSpec, get_adapter
from .adapters.base import AdapterUnavailable


def main() -> None:
    parser = argparse.ArgumentParser(description="只测试打印机连接，不访问飞书")
    parser.add_argument("--brand", required=True, help="bambu/creality/raise3d/snapmaker")
    parser.add_argument("--model", default="", help="具体型号，例如 K1C、A250")
    parser.add_argument("--ip", required=True, help="打印机 IP 地址")
    parser.add_argument("--serial", default="", help="序列号；Bambu 必填")
    parser.add_argument("--access-code", default="", help="访问码；Bambu 必填")
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    printer = PrinterSpec(args.brand, args.model, args.ip, args.serial, args.access_code)
    try:
        status = get_adapter(printer.brand).query_status(printer, timeout=args.timeout)
    except AdapterUnavailable as exc:
        print(f"未连接：{exc}")
        return
    print(f"{printer.brand} {printer.model} {printer.ip_address} -> {status}")


if __name__ == "__main__":
    main()
