"""Snapmaker 2.0 local HTTP API adapter."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .base import AdapterUnavailable, PrinterAdapter, PrinterSpec


class SnapmakerAdapter(PrinterAdapter):
    brand = "snapmaker"

    def query_status(self, printer: PrinterSpec, timeout: float = 10) -> str:
        if printer.model.strip().lower() in {"u1", "snapmakeru1"}:
            return self._query_u1(printer, timeout)

        port = int(os.getenv("SNAPMAKER_PORT", "8080"))
        base_url = f"http://{printer.ip_address}:{port}"
        token = None
        try:
            connect_response = self._request(
                f"{base_url}/api/v1/connect", method="POST", timeout=timeout
            )
            token = self._extract_token(connect_response)
            if not token:
                raise ValueError("connect 响应中没有 token，可能需要在打印机屏幕确认连接")

            status_response = self._request(
                f"{base_url}/api/v1/status?{urllib.parse.urlencode({'token': token})}",
                timeout=timeout,
            )
            return self._normalize_status(status_response)
        except urllib.error.HTTPError as exc:
            return f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return f"连接异常: {exc.reason}"
        except TimeoutError:
            return "查询超时"
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return f"响应异常: {type(exc).__name__}"
        finally:
            if token:
                try:
                    self._request(
                        f"{base_url}/api/v1/disconnect?{urllib.parse.urlencode({'token': token})}",
                        method="POST",
                        timeout=timeout,
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    pass

    @classmethod
    def _query_u1(cls, printer: PrinterSpec, timeout: float) -> str:
        port = int(os.getenv("SNAPMAKER_U1_PORT", "7125"))
        url = (
            f"http://{printer.ip_address}:{port}/printer/objects/query"
            "?webhooks&print_stats&virtual_sdcard"
        )
        request = urllib.request.Request(url, method="GET")
        api_key = os.getenv("SNAPMAKER_U1_API_KEY") or printer.access_code
        if api_key:
            request.add_header("X-Api-Key", api_key)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return cls._normalize_moonraker_status(payload)
        except urllib.error.HTTPError as exc:
            return f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return f"连接异常: {exc.reason}"
        except TimeoutError:
            return "查询超时"
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return f"响应异常: {type(exc).__name__}"

    @staticmethod
    def _request(url: str, method: str = "GET", timeout: float = 10):
        request = urllib.request.Request(
            url,
            data=b"{}" if method == "POST" else None,
            method=method,
        )
        if method == "POST":
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _extract_token(payload: dict):
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        if isinstance(data, dict):
            return data.get("token") or data.get("sid")
        return None

    @staticmethod
    def _normalize_status(payload: dict) -> str:
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        raw = data.get("status") or data.get("state") if isinstance(data, dict) else data
        if raw is None:
            return "UNKNOWN"
        value = str(raw).strip().upper()
        return {
            "IDLE": "IDLE",
            "READY": "IDLE",
            "PRINTING": "RUNNING",
            "RUNNING": "RUNNING",
            "PAUSE": "PAUSED",
            "PAUSED": "PAUSED",
            "FINISH": "FINISHED",
            "FINISHED": "FINISHED",
            "COMPLETE": "FINISHED",
            "ERROR": "ERROR",
            "FAILED": "ERROR",
            "OFFLINE": "OFFLINE",
        }.get(value, value)

    @staticmethod
    def _normalize_moonraker_status(payload: dict) -> str:
        result = payload.get("result", payload) if isinstance(payload, dict) else {}
        status = result.get("status", {}) if isinstance(result, dict) else {}
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
