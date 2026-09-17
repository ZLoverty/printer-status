"""Bambu Lab MQTT adapter."""

import json
import ssl
import threading

import paho.mqtt.client as mqtt

from .base import PrinterAdapter, PrinterSpec


class BambuAdapter(PrinterAdapter):
    brand = "bambu"

    def query_status(self, printer: PrinterSpec, timeout: float = 10) -> str:
        result = {"status": None}
        received = threading.Event()
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.username_pw_set("bblp", printer.access_code)
        mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
        mqtt_client.tls_insecure_set(True)
        report_topic = f"device/{printer.serial}/report"
        request_topic = f"device/{printer.serial}/request"

        def on_connect(_client, _userdata, _flags, reason_code, _properties=None):
            if reason_code != 0:
                result["status"] = f"连接失败 ({reason_code})"
                received.set()
                return
            _client.subscribe(report_topic)
            _client.publish(
                request_topic,
                json.dumps({"pushing": {"sequence_id": "0", "command": "pushall"}}),
            )

        def on_message(_client, _userdata, msg):
            try:
                data = json.loads(msg.payload.decode("utf-8"))
                state = data.get("print", {}).get("gcode_state")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return
            if state:
                result["status"] = state
                received.set()

        def on_disconnect(_client, _userdata, _disconnect_flags, reason_code, _properties=None):
            if not received.is_set() and reason_code != 0:
                result["status"] = f"连接断开 ({reason_code})"
                received.set()

        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.on_disconnect = on_disconnect
        try:
            mqtt_client.connect(printer.ip_address, 8883, 10)
            mqtt_client.loop_start()
            if not received.wait(timeout):
                return "查询超时"
            return result["status"] or "未知"
        except Exception as exc:
            return f"连接异常: {type(exc).__name__}"
        finally:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
