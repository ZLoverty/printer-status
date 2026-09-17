"""Creality Moonraker HTTP adapter.

This supports Creality machines that expose Moonraker, such as rooted or
custom-firmware K1-family installations. Stock firmware without Moonraker
will report a connection error rather than being treated as supported.
"""

import json
import os
import urllib.error
import urllib.request

from .base import AdapterUnavailable, PrinterAdapter, PrinterSpec


class CrealityAdapter(PrinterAdapter):
    brand = "creality"

    def query_status(self, printer: PrinterSpec, timeout: float = 10) -> str:
        port = int(os.getenv("CREALITY_PORT", "7125"))
        url = f"http://{printer.ip_address}:{port}/printer/objects/query"
        request_body = json.dumps(
            {
                "objects": {
                    "webhooks": None,
                    "virtual_sdcard": None,
                    "print_stats": None,
                }
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        api_key = os.getenv("CREALITY_API_KEY") or printer.access_code
        if api_key:
            request.add_header("X-Api-Key", api_key)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return self._normalize_status(payload)
        except urllib.error.HTTPError as exc:
            return f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return f"连接异常: {exc.reason}"
        except TimeoutError:
            return "查询超时"
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return f"响应异常: {type(exc).__name__}"

    @staticmethod
    def _normalize_status(payload: dict) -> str:
        data = payload.get("result", payload)
        status = data.get("status", {}) if isinstance(data, dict) else {}
        webhooks = status.get("webhooks", {})
        print_stats = status.get("print_stats", {})
        webhooks_state = str(webhooks.get("state", "")).lower()
        print_state = str(print_stats.get("state", "")).lower()

        if webhooks_state in {"shutdown", "error"} or print_state == "error":
            return "ERROR"
        if webhooks_state not in {"", "ready"}:
            return "OFFLINE"
        return {
            "standby": "IDLE",
            "printing": "RUNNING",
            "paused": "PAUSED",
            "complete": "FINISHED",
            "cancelled": "ERROR",
            "error": "ERROR",
        }.get(print_state, "UNKNOWN")
