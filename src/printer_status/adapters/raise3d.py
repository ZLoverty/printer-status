"""Raise3D adapter placeholder."""

from .base import AdapterUnavailable, PrinterAdapter, PrinterSpec


class Raise3DAdapter(PrinterAdapter):
    brand = "raise3d"

    def query_status(self, printer: PrinterSpec, timeout: float = 10) -> str:
        raise AdapterUnavailable(
            f"尚未实现 Raise3D {printer.model or 'unknown'} 适配器，请先确认协议"
        )
