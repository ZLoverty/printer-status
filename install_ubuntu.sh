#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="${SERVICE_NAME:-printer-status}"
SERVICE_USER="${SERVICE_USER:-$(id -un)}"
VENV_DIR="${VENV_DIR:-${APP_DIR}/.venv}"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
else
    SUDO=(sudo)
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "错误：这个脚本只支持 Debian/Ubuntu 系统。" >&2
    exit 1
fi

if [[ "${SERVICE_USER}" == "root" ]]; then
    echo "错误：不建议以 root 用户运行打印机服务。请使用普通用户执行。" >&2
    exit 1
fi

echo "[1/6] 安装系统依赖"
"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y python3 python3-venv python3-pip ca-certificates

echo "[2/6] 检查配置文件"
if [[ ! -f "${APP_DIR}/.env" ]]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    chmod 600 "${APP_DIR}/.env"
    echo "已创建 ${APP_DIR}/.env，请填写飞书配置后重新执行本脚本。" >&2
    exit 2
fi

for key in FEISHU_APP_ID FEISHU_APP_SECRET FEISHU_APP_TOKEN FEISHU_TABLE_ID; do
    if ! grep -Eq "^[[:space:]]*${key}=[^[:space:]]+" "${APP_DIR}/.env"; then
        echo "错误：.env 缺少或未填写 ${key}" >&2
        exit 1
    fi
done

echo "[3/6] 创建 Python 虚拟环境"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${VENV_DIR}"
fi

echo "[4/6] 安装 printer-status 包"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install "${APP_DIR}"

echo "[5/6] 创建 systemd 服务"
"${SUDO[@]}" install -d -m 755 "$(dirname -- "${UNIT_FILE}")"
"${SUDO[@]}" tee "${UNIT_FILE}" >/dev/null <<EOF
[Unit]
Description=Feishu Bitable Bambu Printer Status Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${VENV_DIR}/bin/printer-status
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "[6/6] 启用并启动服务"
"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable --now "${SERVICE_NAME}.service"

echo
echo "安装完成。"
echo "查看状态：sudo systemctl status ${SERVICE_NAME}"
echo "查看日志：sudo journalctl -u ${SERVICE_NAME} -f"
