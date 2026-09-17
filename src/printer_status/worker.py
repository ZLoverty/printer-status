"""Poll Bambu printers and update their status in a Feishu Bitable."""

import os
import time
from pathlib import Path

import lark_oapi as lark
from dotenv import load_dotenv
from lark_oapi.api.bitable.v1 import (
    AppTableRecord,
    ListAppTableRecordRequest,
    UpdateAppTableRecordRequest,
)
from .adapters import PrinterSpec, get_adapter
from .adapters.base import AdapterUnavailable


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
BRAND_FIELD = os.getenv("BRAND_FIELD", "brand")
MODEL_FIELD = os.getenv("MODEL_FIELD", "model")

client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()


def query_printer(printer: PrinterSpec) -> str:
    """通过对应品牌适配器查询状态。"""
    try:
        return get_adapter(printer.brand).query_status(printer, timeout=MQTT_TIMEOUT)
    except AdapterUnavailable as exc:
        return f"未支持: {exc}"


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
        brand = str(fields.get(BRAND_FIELD) or "bambu").strip()
        model = str(fields.get(MODEL_FIELD) or "").strip()
        if not ip_address:
            print(f"[跳过] record={record_id}: 缺少 {IP_FIELD}")
            continue
        if brand.lower().replace(" ", "") in {"bambu", "bambulab"} and (
            not serial or not access_code
        ):
            print(f"[跳过] record={record_id}: Bambu 缺少 {SERIAL_FIELD}/{ACCESS_CODE_FIELD}")
            continue
        status = query_printer(
            PrinterSpec(brand, model, ip_address, serial, access_code)
        )
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
