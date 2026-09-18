# printer-status-bitable

轮询 Bambu Lab 打印机，并把 `gcode_state` 回填到飞书多维表格的 `status` 字段。

## 安装

在项目目录执行：

```bash
python -m pip install .
```

开发模式安装：

```bash
python -m pip install -e .
```

## 配置

```bash
cp .env.example .env
```

填写 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_APP_TOKEN`、`FEISHU_TABLE_ID`。
表格需要包含 `ip_address`、`serial`、`access_code`、`status` 四列。
如果需要混用多个品牌，增加 `brand` 和 `model` 两列；未填写 `brand` 的旧记录默认按 `bambu` 处理。

## 独立测试打印机连接

探测命令不访问飞书，只调用对应打印机适配器：

```bash
printer-status-probe --brand bambu --model X1C \
  --ip 192.168.1.20 --serial SERIAL --access-code ACCESS_CODE
```

测试 Raise3D：

```bash
printer-status-probe --brand raise3d --model Pro3 \
  --ip 192.168.1.21 --access-code RAISE_API_PASSWORD
```

Raise3D 需要先在打印机的 `Machine > Developer` 中启用 Remote Access API，并设置 Access Password。默认 API 端口是 `10800`，可用 `RAISE3D_PORT` 覆盖。

测试暴露 Moonraker 的创想打印机：

```bash
printer-status-probe --brand creality --model K1C \
  --ip 192.168.1.22 --access-code CREALITY_API_KEY
```

默认访问 `7125` 端口的 Moonraker API，可用 `CREALITY_PORT` 覆盖。若没有开启 Moonraker，原厂固件通常不能通过这个适配器查询状态。

目前 Bambu 和 Raise3D 局域网适配器已接入；Creality、Snapmaker 已建立兼容层入口，具体型号协议确认后再实现。

## 运行

首次测试只运行一轮：

```bash
printer-status --once
```

持续轮询：

```bash
printer-status
```

也可以使用：

```bash
python -m printer_status --once
```

## Ubuntu Server 部署

将项目目录放到服务器后，执行：

```bash
chmod +x install_ubuntu.sh
./install_ubuntu.sh
```

第一次执行会创建 `.env` 模板并退出。填写飞书配置后再次执行，脚本会安装依赖、创建 systemd 服务，并设置开机自动启动。

查看服务状态和日志：

```bash
sudo systemctl status printer-status
sudo journalctl -u printer-status -f
```

## 测试 Snapmaker 2.0

```bash
printer-status-probe --brand snapmaker --model A250 \
  --ip 192.168.1.23
```

默认访问 `8080` 端口。首次连接时可能需要在打印机触摸屏确认；如果 `connect` 没有返回 token，探测命令会提示这一点。

Snapmaker U1 使用 Moonraker，命令中的 `--model` 必须填写 `U1`，适配器会自动改用 `7125` 端口：

```bash
printer-status-probe --brand snapmaker --model U1 \
  --ip 192.168.113.131
```

可用 `SNAPMAKER_U1_PORT` 和 `SNAPMAKER_U1_API_KEY` 覆盖默认配置。J1、Artisan 等产品线协议可能不同，暂不按 U1 接口处理。

## 使用率统计

在多维表格主表增加三个数字字段：`utilization`、`busy_seconds`、`observed_seconds`。程序会在本地 SQLite 文件 `.data/printer_status.db` 中记录每轮采样，并将累计使用率回填到主表。

默认将 `RUNNING`、`PAUSED`、`BUSY` 计为忙碌，将 `IDLE`、`FINISHED` 计为空闲；`OFFLINE`、`UNKNOWN` 和查询超时不计入有效观测时间。程序会统一识别 `PRINTING/RUNNING`、`PAUSE/PAUSED`、`FINISH/FINISHED` 等别名。`MAX_COUNTED_GAP` 默认 900 秒，用于避免服务长时间停止后把停机时间算作使用时间。
