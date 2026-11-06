#!/usr/bin/env bash
# DowntimeLess master installer and manager.
#   bash <(curl -fsSL https://raw.githubusercontent.com/Emadhabibnia1385/DowntimeLess/main/install.sh)
# After the first run use:  sudo downtimeless
set -Eeuo pipefail

REPO="${DL_REPO:-https://github.com/Emadhabibnia1385/DowntimeLess.git}"
BRANCH="${DL_BRANCH:-main}"
APP_DIR="${DL_APP_DIR:-/opt/downtimeless}"
CONF_DIR="/etc/downtimeless"
ENV_FILE="$CONF_DIR/master.env"
LANG_FILE="$CONF_DIR/lang"
DATA_DIR="${DL_DATA_DIR:-/var/lib/downtimeless}"
SERVICE="downtimeless"
UNIT="/etc/systemd/system/$SERVICE.service"
NGINX_SITE="/etc/nginx/conf.d/downtimeless.conf"
LAUNCHER="/usr/local/bin/downtimeless"
RUN_USER="downtimeless"

R='\033[31m'; G='\033[32m'; Y='\033[33m'; C='\033[36m'; M='\033[35m'; B='\033[1m'; D='\033[2m'; N='\033[0m'

# ---------- messages (fa / en) ----------
declare -A FA EN
EN[need_root]="Run as root: sudo bash install.sh"
FA[need_root]="با کاربر root اجرا کنید: sudo bash install.sh"
EN[choose_lang]="Language / زبان:  1) فارسی   2) English"
FA[choose_lang]="Language / زبان:  1) فارسی   2) English"
EN[tagline]="VPN fleet monitoring and management"
FA[tagline]="مانیتور و مدیریت سرورهای VPN"
EN[dev]="Developer"
FA[dev]="توسعه‌دهنده"
EN[status_label]="Status"
FA[status_label]="وضعیت"
EN[online]="Running"
FA[online]="در حال اجرا"
EN[offline]="Stopped"
FA[offline]="متوقف"
EN[not_installed]="Not installed"
FA[not_installed]="نصب نشده"
EN[m_install]="Install"
FA[m_install]="نصب"
EN[m_update]="Update"
FA[m_update]="به‌روزرسانی"
EN[m_env]="Edit settings (.env)"
FA[m_env]="ویرایش تنظیمات (.env)"
EN[m_status]="Status"
FA[m_status]="وضعیت"
EN[m_logs]="Live logs"
FA[m_logs]="لاگ زنده"
EN[m_restart]="Restart"
FA[m_restart]="ریستارت"
EN[m_claim]="Panel address and owner link"
FA[m_claim]="آدرس پنل و لینک مالک"
EN[m_backup]="Backup database"
FA[m_backup]="بکاپ دیتابیس"
EN[m_uninstall]="Uninstall"
FA[m_uninstall]="حذف"
EN[m_exit]="Exit"
FA[m_exit]="خروج"
EN[m_lang]="Change language"
FA[m_lang]="تغییر زبان"
EN[prompt]="Choose"
FA[prompt]="انتخاب کنید"
EN[invalid]="Invalid option"
FA[invalid]="گزینهٔ نامعتبر"
EN[press_enter]="Press Enter to continue..."
FA[press_enter]="برای ادامه Enter بزنید..."
EN[ask_domain]="Panel domain, for example panel.example.com (empty = IP only)"
FA[ask_domain]="دامنهٔ پنل، مثلاً panel.example.com (خالی = فقط با IP)"
EN[ask_token]="Telegram bot token from @BotFather"
FA[ask_token]="توکن ربات تلگرام از @BotFather"
EN[ask_port]="Local port"
FA[ask_port]="پورت داخلی"
EN[ask_tls]="TLS: 1) Cloudflare/other proxy terminates TLS   2) Let's Encrypt with certbot   3) none (http)"
FA[ask_tls]="TLS: ۱) Cloudflare یا پروکسی دیگر   ۲) Let's Encrypt با certbot   ۳) بدون TLS (http)"
EN[bad_token]="The bot token was rejected by Telegram."
FA[bad_token]="تلگرام این توکن ربات را قبول نکرد."
EN[installing_pkgs]="Installing system packages"
FA[installing_pkgs]="نصب بسته‌های سیستم"
EN[fetching]="Downloading DowntimeLess"
FA[fetching]="دریافت DowntimeLess"
EN[venv]="Preparing the Python environment"
FA[venv]="آماده‌سازی محیط پایتون"
EN[writing]="Writing configuration and service"
FA[writing]="نوشتن تنظیمات و سرویس"
EN[nginx_on]="nginx site created"
FA[nginx_on]="سایت nginx ساخته شد"
EN[nginx_fail]="nginx config test failed; the site file was removed"
FA[nginx_fail]="آزمون تنظیم nginx ناموفق بود؛ فایل سایت حذف شد"
EN[waiting]="Waiting for the panel to answer"
FA[waiting]="منتظر پاسخ پنل"
EN[healthy]="Panel is healthy"
FA[healthy]="پنل سالم است"
EN[unhealthy]="Panel did not become healthy; last log lines:"
FA[unhealthy]="پنل سالم بالا نیامد؛ آخرین خط‌های لاگ:"
EN[panel_url]="Panel address"
FA[panel_url]="آدرس پنل"
EN[owner_link]="Open this link in Telegram ONCE to become the owner"
FA[owner_link]="این لینک را فقط یک بار در تلگرام باز کنید تا مالک پنل شوید"
EN[owner_done]="An owner already exists; no claim link is pending."
FA[owner_done]="مالک قبلاً ثبت شده؛ لینکی در انتظار نیست."
EN[updated]="Updated"
FA[updated]="به‌روز شد"
EN[rolled_back]="Update failed, rolled back to the previous version"
FA[rolled_back]="به‌روزرسانی ناموفق بود؛ به نسخهٔ قبلی برگشت"
EN[env_menu]="1) Bot token   2) Public URL   3) Port   4) Open in editor   0) Back"
FA[env_menu]="۱) توکن ربات   ۲) آدرس عمومی   ۳) پورت   ۴) باز کردن در ویرایشگر   ۰) بازگشت"
EN[saved_restart]="Saved. Restarting the service"
FA[saved_restart]="ذخیره شد. سرویس ریستارت می‌شود"
EN[backup_done]="Backup written to"
FA[backup_done]="بکاپ نوشته شد در"
EN[confirm_rm]="Remove DowntimeLess? Type yes to continue"
FA[confirm_rm]="DowntimeLess حذف شود؟ برای ادامه yes بنویسید"
EN[keep_data]="Delete the database and data too? [y/N]"
FA[keep_data]="دیتابیس و داده‌ها هم پاک شوند؟ [y/N]"
EN[removed]="Removed"
FA[removed]="حذف شد"
EN[agent_hint]="Add servers in the panel; it shows a one-line agent install command for each."
FA[agent_hint]="سرورها را از داخل پنل اضافه کنید؛ برای هر کدام یک دستور نصب agent نشان می‌دهد."

L=""
m() { if [[ "$L" == "fa" ]]; then printf '%s' "${FA[$1]:-$1}"; else printf '%s' "${EN[$1]:-$1}"; fi; }

ok()   { echo -e "${G}✓${N} $*"; }
info() { echo -e "${Y}➜${N} $*"; }
err()  { echo -e "${R}✗${N} $*" >&2; exit 1; }
trap 'echo -e "${R}✗ line $LINENO${N}" >&2' ERR

need_root() { [[ $EUID -eq 0 ]] || err "$(m need_root)"; }

load_lang() {
  if [[ -r "$LANG_FILE" ]]; then L="$(cat "$LANG_FILE")"; return; fi
  [[ -t 0 ]] || { L="en"; return; }
  echo -e "${C}$(m choose_lang)${N}"
  read -r -p "> " c </dev/tty
  [[ "$c" == "2" ]] && L="en" || L="fa"
  mkdir -p "$CONF_DIR"; echo "$L" > "$LANG_FILE"
}

env_get() { [[ -r "$ENV_FILE" ]] && sed -n "s/^$1=//p" "$ENV_FILE" | head -1 || true; }
env_set() {
  touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
  if grep -q "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi
}
ask() { local v; read -r -p "$(echo -e "${C}$1${N} [${2:-}]: ")" v </dev/tty; echo "${v:-${2:-}}"; }
sane() { [[ "$1" =~ ^[A-Za-z0-9:._/@+-]*$ ]] || err "unsafe characters in value"; }

installed() { [[ -d "$APP_DIR/.git" && -f "$UNIT" ]]; }
running()   { systemctl is-active --quiet "$SERVICE" 2>/dev/null; }

header() {
  clear
  echo -e "${B}${C}╔══════════════════════════════════════════════╗${N}"
  echo -e "${B}${C}║${N}  ${B}🛡  DowntimeLess${N}  ${D}$(m tagline)${N}"
  echo -e "${B}${C}║${N}  ${D}$(m dev): @emadhabibnia · github.com/emadhabibnia1385${N}"
  echo -e "${B}${C}╚══════════════════════════════════════════════╝${N}"
  local s
  if ! installed; then s="${Y}$(m not_installed)${N}"; elif running; then s="${G}🟢 $(m online)${N}"; else s="${R}🔴 $(m offline)${N}"; fi
  echo -e " $(m status_label): $s\n"
}

pkgs() {
  info "$(m installing_pkgs)"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 python3-venv python3-pip git curl ca-certificates nginx >/dev/null
}

fetch_code() {
  info "$(m fetching)"
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" fetch -q origin "$BRANCH"
    git -C "$APP_DIR" reset -q --hard "origin/$BRANCH"
  else
    git clone -q --branch "$BRANCH" "$REPO" "$APP_DIR"
  fi
}

setup_venv() {
  info "$(m venv)"
  [[ -x "$APP_DIR/venv/bin/python" ]] || python3 -m venv "$APP_DIR/venv"
  "$APP_DIR/venv/bin/pip" install -q --upgrade pip
  "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/master/requirements.txt"
}

write_unit() {
  local port; port="$(env_get DL_PORT)"
  id "$RUN_USER" >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$RUN_USER"
  mkdir -p "$DATA_DIR"; chown -R "$RUN_USER" "$DATA_DIR"; chmod 700 "$DATA_DIR"
  cat > "$UNIT" <<EOF
[Unit]
Description=DowntimeLess master
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$APP_DIR/master
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port ${port:-7390} --proxy-headers --no-server-header
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=$DATA_DIR

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "$UNIT"
  systemctl daemon-reload
  systemctl enable "$SERVICE" >/dev/null 2>&1
}

write_nginx() {
  local domain port tls; domain="$(env_get DL_DOMAIN)"; port="$(env_get DL_PORT)"; tls="$(env_get DL_TLS)"
  [[ -n "$domain" ]] || return 0
  cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    server_name $domain;
    client_max_body_size 2m;
    location / {
        proxy_pass http://127.0.0.1:${port:-7390};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx; ok "$(m nginx_on): $domain"
    if [[ "$tls" == "certbot" ]]; then
      apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
      certbot --nginx -d "$domain" --non-interactive --agree-tos --register-unsafely-without-email --redirect || info "certbot failed; the panel stays on http"
    fi
  else
    rm -f "$NGINX_SITE"; nginx -t >/dev/null 2>&1 || true; err "$(m nginx_fail)"
  fi
}

wait_healthy() {
  local port; port="$(env_get DL_PORT)"
  info "$(m waiting)"
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${port:-7390}/api/v1/health" >/dev/null 2>&1; then ok "$(m healthy)"; return 0; fi
    sleep 1
  done
  echo -e "${R}$(m unhealthy)${N}"; journalctl -u "$SERVICE" -n 25 --no-pager || true
  return 1
}

show_access() {
  local url claim; url="$(env_get DL_PUBLIC_URL)"
  echo -e "\n${B}$(m panel_url):${N} ${G}$url${N}"
  claim="$DATA_DIR/claim_link.txt"
  for _ in $(seq 1 10); do [[ -s "$claim" ]] && break; sleep 1; done
  if [[ -s "$claim" ]]; then
    echo -e "${B}$(m owner_link):${N}\n${M}$(cat "$claim")${N}"
  else
    echo -e "${D}$(m owner_done)${N}"
  fi
  echo -e "\n${D}$(m agent_hint)${N}"
}

do_install() {
  need_root
  local domain token port tls scheme url
  domain="$(ask "$(m ask_domain)" "$(env_get DL_DOMAIN)")"; sane "$domain"
  while true; do
    token="$(ask "$(m ask_token)" "$(env_get DL_BOT_TOKEN)")"; sane "$token"
    if curl -fsS "https://api.telegram.org/bot${token}/getMe" >/dev/null 2>&1; then break; fi
    echo -e "${R}$(m bad_token)${N}"
  done
  port="$(ask "$(m ask_port)" "$(env_get DL_PORT || true)")"; port="${port:-7390}"; sane "$port"
  tls="none"; scheme="http"
  if [[ -n "$domain" ]]; then
    case "$(ask "$(m ask_tls)" "1")" in
      2) tls="certbot"; scheme="https" ;;
      3) tls="none"; scheme="http" ;;
      *) tls="proxy"; scheme="https" ;;
    esac
    url="$scheme://$domain"
  else
    url="http://$(hostname -I | awk '{print $1}'):$port"
  fi
  pkgs; fetch_code; setup_venv
  info "$(m writing)"
  mkdir -p "$CONF_DIR"; chmod 700 "$CONF_DIR"
  env_set DL_DOMAIN "$domain"; env_set DL_TLS "$tls"; env_set DL_PORT "$port"
  env_set DL_BOT_TOKEN "$token"; env_set DL_PUBLIC_URL "$url"
  env_set DL_DATA_DIR "$DATA_DIR"; env_set DL_COOKIE_SECURE "$([[ $scheme == https ]] && echo true || echo false)"
  write_unit; install_launcher
  systemctl restart "$SERVICE"
  write_nginx
  wait_healthy && show_access
}

do_update() {
  need_root; installed || err "$(m not_installed)"
  local prev; prev="$(git -C "$APP_DIR" rev-parse HEAD)"
  fetch_code; setup_venv; write_unit
  systemctl restart "$SERVICE"
  if wait_healthy; then ok "$(m updated): $(git -C "$APP_DIR" rev-parse --short HEAD)"; else
    git -C "$APP_DIR" reset -q --hard "$prev"; setup_venv; systemctl restart "$SERVICE"
    err "$(m rolled_back)"
  fi
}

do_env() {
  need_root; installed || err "$(m not_installed)"
  echo -e "$(m env_menu)"
  read -r -p "> " c </dev/tty
  case "$c" in
    1|۱) local t; t="$(ask "$(m ask_token)" "")"; sane "$t"; [[ -n "$t" ]] && env_set DL_BOT_TOKEN "$t" ;;
    2|۲) local u; u="$(ask "$(m panel_url)" "$(env_get DL_PUBLIC_URL)")"; sane "$u"; env_set DL_PUBLIC_URL "$u" ;;
    3|۳) local p; p="$(ask "$(m ask_port)" "$(env_get DL_PORT)")"; sane "$p"; env_set DL_PORT "$p"; write_unit; write_nginx ;;
    4|۴) "${EDITOR:-nano}" "$ENV_FILE" ;;
    *) return 0 ;;
  esac
  info "$(m saved_restart)"; systemctl restart "$SERVICE"; wait_healthy || true
}

do_status() { systemctl status "$SERVICE" --no-pager -l | head -25 || true; }
do_logs()   { journalctl -u "$SERVICE" -f -n 50; }
do_restart(){ need_root; systemctl restart "$SERVICE"; wait_healthy || true; }
do_claim()  { installed || err "$(m not_installed)"; show_access; }

do_backup() {
  need_root; installed || err "$(m not_installed)"
  local out; out="/var/backups/downtimeless-$(date +%Y%m%d-%H%M%S).db"
  "$APP_DIR/venv/bin/python" - "$DATA_DIR/downtimeless.db" "$out" <<'PY'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
src.backup(dst)
PY
  chmod 600 "$out"; ok "$(m backup_done) $out"
}

do_uninstall() {
  need_root
  local a; a="$(ask "$(m confirm_rm)" "")"; [[ "$a" == "yes" ]] || return 0
  systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
  rm -f "$UNIT" "$NGINX_SITE" "$LAUNCHER"; systemctl daemon-reload
  nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  case "$(ask "$(m keep_data)" "n")" in y|Y) rm -rf "$DATA_DIR" ;; esac
  rm -rf "$APP_DIR" "$CONF_DIR"
  ok "$(m removed)"
}

install_launcher() {
  cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec bash "$APP_DIR/install.sh" "\$@"
EOF
  chmod 755 "$LAUNCHER"
}

pause() { read -r -p "$(m press_enter)" _ </dev/tty || true; }

menu() {
  while true; do
    header
    echo -e " ${B}${G}1)${N} 📦 $(m m_install)      ${B}${G}2)${N} ⬆️  $(m m_update)"
    echo -e " ${B}${C}3)${N} ⚙️  $(m m_env)      ${B}${C}4)${N} 📊 $(m m_status)"
    echo -e " ${B}${C}5)${N} 📜 $(m m_logs)      ${B}${Y}6)${N} 🔄 $(m m_restart)"
    echo -e " ${B}${M}7)${N} 🔗 $(m m_claim)"
    echo -e " ${B}${M}8)${N} 💾 $(m m_backup)    ${B}${R}9)${N} 🗑  $(m m_uninstall)"
    echo -e " ${B}${C}l)${N} 🌐 $(m m_lang)      ${B}0)${N} $(m m_exit)\n"
    read -r -p "$(echo -e "${C}$(m prompt)${N} ${B}➜${N} ")" c </dev/tty || exit 0
    case "$c" in
      1) do_install ;; 2) do_update ;; 3) do_env ;; 4) do_status ;;
      5) do_logs ;; 6) do_restart ;; 7) do_claim ;; 8) do_backup ;; 9) do_uninstall ;;
      l|L) rm -f "$LANG_FILE"; load_lang; continue ;;
      0|q) exit 0 ;;
      *) echo -e "${R}$(m invalid)${N}"; sleep 1; continue ;;
    esac
    pause
  done
}

main() {
  need_root
  load_lang
  case "${1:-}" in
    install) do_install ;; update) do_update ;; env) do_env ;; status) do_status ;;
    logs) do_logs ;; restart) do_restart ;; claim) do_claim ;; backup) do_backup ;;
    uninstall) do_uninstall ;; "") [[ -t 0 ]] || exec < /dev/tty; menu ;;
    *) echo "usage: downtimeless [install|update|env|status|logs|restart|claim|backup|uninstall]"; exit 2 ;;
  esac
}

# source-only guard so tests can load the functions
if [[ "${DL_SOURCE_ONLY:-0}" != "1" ]]; then main "$@"; fi
