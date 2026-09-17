"""Poll Bambu printers and update their status in a Feishu Bitable."""

import json
import os
import ssl
import threading
import time
from pathlib import Path

import lark_oapi as lark
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from lark_oapi.api.bitable.v1 import (
    AppTableRecord,
    ListAppTableRecordRequest,
    UpdateAppTableRecordRequest,
)


load_dotenv(Path.cwd() / ".env")
load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"缺少环境变量: {name}")
    return value


APP_ID = _required("FEISHU_APP_ID")
APP_SECRET = _required("FEISHU_APP_SECRET")
APP_TOKEN = _required("FEISHU_APP_TOKEN")
TABLE_ID = _required("FEISHU_TABLE_ID")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))
MQTT_TIMEOUT = float(os.getenv("MQTT_TIMEOUT", "10"))
IP_FIELD = os.getenv("IP_FIELD", "ip_address")
SERIAL_FIELD = os.getenv("SERIAL_FIELD", "serial")
ACCESS_CODE_FIELD = os.getenv("ACCESS_CODE_FIELD", "access_code")
STATUS_FIELD = os.getenv("STATUS_FIELD", "status")

client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()


def query_printer(ip_address: str, serial: str, access_code: str) -> str:
    """通过 MQTT 查询一台打印机，返回 gcode_state 或连接错误。"""
    result = {"status": None}
    received = threading.Event()
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.username_pw_set("bblp", access_code)
    mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
    mqtt_client.tls_insecure_set(True)
    report_topic = f"device/{serial}/report"
    request_topic = f"device/{serial}/request"

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
        mqtt_client.connect(ip_address, 8883, 10)
        mqtt_client.loop_start()
        if not received.wait(MQTT_TIMEOUT):
            return "查询超时"
        return result["status"] or "未知"
    except Exception as exc:
        return f"连接异常: {type(exc).__name__}"
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


def fetch_all_records():
    """分页读取全部表格记录。"""
    records = []
    page_token = None
    while True:
        builder = (
            ListAppTableRecordRequest.builder()
            .app_token(APP_TOKEN)
            .table_id(TABLE_ID)
            .page_size(500)
        )
        if page_token:
            builder.page_token(page_token)
        response = client.bitable.v1.app_table_record.list(builder.build())
        if not response.success():
            print(f"[拉取失败] code={response.code} msg={response.msg}")
            break
        records.extend((item.record_id, item.fields) for item in (response.data.items or []))
        if not response.data.has_more:
            break
        page_token = response.data.page_token
    return records


def update_status(record_id: str, status: str):
    body = AppTableRecord.builder().fields({STATUS_FIELD: status}).build()
    request = (
        UpdateAppTableRecordRequest.builder()
        .app_token(APP_TOKEN)
        .table_id(TABLE_ID)
        .record_id(record_id)
        .request_body(body)
        .build()
    )
    response = client.bitable.v1.app_table_record.update(request)
    if not response.success():
        print(f"[更新失败] record={record_id} code={response.code} msg={response.msg}")
    return response.success()


def poll_once():
    for record_id, fields in fetch_all_records():
        ip_address = str(fields.get(IP_FIELD) or "").strip()
        serial = str(fields.get(SERIAL_FIELD) or "").strip()
        access_code = str(fields.get(ACCESS_CODE_FIELD) or "").strip()
        if not ip_address or not serial or not access_code:
            print(f"[跳过] record={record_id}: 缺少 {IP_FIELD}/{SERIAL_FIELD}/{ACCESS_CODE_FIELD}")
            continue
        status = query_printer(ip_address, serial, access_code)
        update_status(record_id, status)
        print(f"[同步] {serial} ({ip_address}) -> {status}")


def main(once: bool = False):
    print(f"开始轮询打印机，每 {POLL_INTERVAL}s 更新一次；Ctrl+C 退出")
    while True:
        try:
            poll_once()
        except Exception as exc:
            print(f"[本轮失败] {type(exc).__name__}: {exc}")
        if once:
            return
        time.sleep(POLL_INTERVAL)
