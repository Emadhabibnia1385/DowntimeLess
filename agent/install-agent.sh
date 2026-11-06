#!/bin/bash
set -Eeuo pipefail

# DowntimeLess agent installer. Re-running it updates the agent in place.
#   curl -fsSL https://<panel>/agent/install.sh | sudo bash -s -- --master https://<panel> --token <enroll>
#   ./install-agent.sh --uninstall

APP_DIR="/opt/downtimeless-agent"
AGENT_BIN="${APP_DIR}/agent.py"
CONF_DIR="/etc/downtimeless"
CONF_FILE="${DL_AGENT_CONFIG:-${CONF_DIR}/agent.json}"
SERVICE="downtimeless-agent"
UNIT_FILE="/etc/systemd/system/${SERVICE}.service"

MASTER="${DL_MASTER:-}"
TOKEN="${DL_TOKEN:-}"
UNINSTALL=0

R='\033[31m'; G='\033[32m'; Y='\033[33m'; C='\033[36m'; B='\033[1m'; N='\033[0m'
ok()   { echo -e "${G}✓ $*${N}"; }
info() { echo -e "${Y}➜ $*${N}"; }
err()  { echo -e "${R}✗ $*${N}" >&2; }
die()  { err "$*"; exit 1; }

usage() {
  echo -e "${B}DowntimeLess agent installer${N}"
  echo "  --master URL    panel address, e.g. https://panel.example.com (env DL_MASTER)"
  echo "  --token TOKEN   one-time enroll token from the panel (env DL_TOKEN)"
  echo "  --uninstall     stop the agent and remove it"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --master)    [ $# -ge 2 ] || die "--master needs a value"; MASTER="$2"; shift 2 ;;
    --token)     [ $# -ge 2 ] || die "--token needs a value"; TOKEN="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *)           usage; die "unknown argument: $1" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "run as root (use sudo)"
command -v systemctl >/dev/null 2>&1 || die "systemd is required"

uninstall() {
  info "Removing ${SERVICE}"
  systemctl disable --now "${SERVICE}" >/dev/null 2>&1 || true
  rm -f "${UNIT_FILE}"
  systemctl daemon-reload
  rm -rf "${APP_DIR}" "${CONF_DIR}"
  ok "Agent removed"
}

if [ "${UNINSTALL}" -eq 1 ]; then
  uninstall
  exit 0
fi

command -v python3 >/dev/null 2>&1 || die "python3 is required (apt install python3)"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' || die "python3 >= 3.8 is required"
command -v curl >/dev/null 2>&1 || die "curl is required (apt install curl)"

[[ "${MASTER}" =~ ^https?://[^/]+ ]] || die "--master must look like https://panel.example.com"
MASTER="${MASTER%/}"
PYTHON="$(command -v python3)"

echo -e "${C}${B}DowntimeLess agent${N}"

info "Downloading agent from ${MASTER}"
mkdir -p "${APP_DIR}"
TMP="$(mktemp "${APP_DIR}/.agent.XXXXXX")"
trap 'rm -f "${TMP}"' EXIT
curl -fsSL --connect-timeout 10 --max-time 60 "${MASTER}/agent/agent.py" -o "${TMP}" \
  || die "could not download ${MASTER}/agent/agent.py"
VERSION="$("${PYTHON}" "${TMP}" version)" || die "downloaded agent does not run"
chmod 0755 "${TMP}"
mv -f "${TMP}" "${AGENT_BIN}"
ok "Agent ${VERSION} installed at ${AGENT_BIN}"

enrolled_master=""
if [ -f "${CONF_FILE}" ]; then
  enrolled_master="$("${PYTHON}" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("master",""))' "${CONF_FILE}" 2>/dev/null || true)"
fi
if [ "${enrolled_master}" = "${MASTER}" ]; then
  ok "Already enrolled with ${MASTER}, keeping the existing key"
else
  [ -n "${TOKEN}" ] || die "--token is required for the first install"
  info "Enrolling with ${MASTER}"
  DL_AGENT_CONFIG="${CONF_FILE}" "${PYTHON}" "${AGENT_BIN}" enroll --master "${MASTER}" --token "${TOKEN}" \
    || die "enroll failed (the token is single-use; create a new one in the panel)"
  ok "Enrolled"
fi

info "Writing ${UNIT_FILE}"
# No NoNewPrivileges/ProtectSystem: the agent runs systemctl and schedules reboots and upgrades.
cat > "${UNIT_FILE}" <<EOF
[Unit]
Description=DowntimeLess agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
Environment=DL_AGENT_CONFIG=${CONF_FILE}
ExecStart=${PYTHON} ${AGENT_BIN} run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "${UNIT_FILE}"

systemctl daemon-reload
systemctl enable "${SERVICE}" >/dev/null 2>&1
systemctl restart "${SERVICE}"
sleep 2

if systemctl is-active --quiet "${SERVICE}"; then
  ok "${SERVICE} is running"
else
  err "${SERVICE} is not running"
  journalctl -u "${SERVICE}" -n 20 --no-pager >&2 || true
  exit 1
fi
systemctl status "${SERVICE}" --no-pager -l | head -n 8 || true
echo -e "${G}${B}Done.${N} Logs: journalctl -u ${SERVICE} -f"
