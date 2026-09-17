"""Common adapter contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PrinterSpec:
    brand: str
    model: str
    ip_address: str
    serial: str = ""
    access_code: str = ""


class AdapterUnavailable(RuntimeError):
    """The selected brand/model adapter is not implemented yet."""


class PrinterAdapter:
    """Interface implemented by each printer brand/protocol."""

    brand = "unknown"

    def query_status(self, printer: PrinterSpec, timeout: float = 10) -> str:
        raise NotImplementedError
