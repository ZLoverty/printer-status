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

目前 Bambu 适配器已接入；Creality、Raise3D、Snapmaker 已建立兼容层入口，具体型号协议确认后再实现，避免把不兼容的协议误写进主流程。

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
