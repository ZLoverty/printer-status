"""Printer protocol adapters."""

from .base import PrinterAdapter, PrinterSpec
from .registry import get_adapter, supported_brands

__all__ = ["PrinterAdapter", "PrinterSpec", "get_adapter", "supported_brands"]
