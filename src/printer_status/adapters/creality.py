"""Creality adapter placeholder."""

from .base import AdapterUnavailable, PrinterAdapter, PrinterSpec


class CrealityAdapter(PrinterAdapter):
    brand = "creality"

    def query_status(self, printer: PrinterSpec, timeout: float = 10) -> str:
        raise AdapterUnavailable(
            f"尚未实现 Creality {printer.model or 'unknown'} 适配器，请先确认协议"
        )
