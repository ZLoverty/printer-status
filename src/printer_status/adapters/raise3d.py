"""Raise3D RaiseTouch local HTTP API adapter."""

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import AdapterUnavailable, PrinterAdapter, PrinterSpec


class Raise3DAdapter(PrinterAdapter):
    brand = "raise3d"

    def query_status(self, printer: PrinterSpec, timeout: float = 10) -> str:
        if not printer.access_code:
            raise AdapterUnavailable("Raise3D 缺少 API Access Password")

        port = int(os.getenv("RAISE3D_PORT", "10800"))
        base_url = f"http://{printer.ip_address}:{port}"

        try:
            token = self._login(base_url, printer.access_code, timeout)
            payload = self._get(
                f"{base_url}/v1/printer/runningstatus",
                {"token": token},
                timeout,
            )
            return self._normalize_status(payload)
        except urllib.error.HTTPError as exc:
            return f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return f"连接异常: {exc.reason}"
        except TimeoutError:
            return "查询超时"
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return f"响应异常: {type(exc).__name__}"

    @staticmethod
    def _sign(password: str, timestamp: int) -> str:
        """RaiseTouch API: MD5(SHA1('password=...&timestamp=...'))."""
        source = f"password={password}&timestamp={timestamp}".encode()
        sha1 = hashlib.sha1(source).hexdigest()
        return hashlib.md5(sha1.encode()).hexdigest()

    @classmethod
    def _login(cls, base_url: str, password: str, timeout: float):
        timestamp = int(time.time() * 1000)
        query = urllib.parse.urlencode(
            {"sign": cls._sign(password, timestamp), "timestamp": timestamp}
        )
        payload = cls._get(f"{base_url}/v1/login?{query}", {}, timeout)
        data = payload.get("data", payload)
        if isinstance(data, dict):
            token = data.get("token")
        else:
            token = data
        if not token:
            raise ValueError("登录响应中没有 token")
        return token

    @staticmethod
    def _get(url: str, params: dict, timeout: float):
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("status") not in (None, 1, "1", True):
            error = body.get("error") or {}
            raise ValueError(error.get("msg", "Raise3D API 返回失败"))
        return body

    @staticmethod
    def _normalize_status(payload: dict) -> str:
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            return str(data)
        raw = data.get("status") or data.get("running_status") or data.get("state")
        if isinstance(raw, dict):
            raw = raw.get("value") or raw.get("name") or raw.get("status")
        if raw is None:
            return "未知"
        value = str(raw).strip().lower()
        mapping = {
            "idle": "IDLE",
            "standby": "IDLE",
            "paused": "PAUSED",
            "pause": "PAUSED",
            "running": "RUNNING",
            "printing": "RUNNING",
            "busy": "BUSY",
            "completed": "FINISHED",
            "complete": "FINISHED",
            "done": "FINISHED",
            "error": "ERROR",
            "offline": "OFFLINE",
        }
        return mapping.get(value, str(raw))
