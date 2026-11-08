import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import bot, monitor
from .db import connect, migrate
from .errors import DLError, dl_error_handler
from .features.agent.router import router as agent_router
from .features.auth.router import router as auth_router
from .features.categories.router import router as categories_router
from .features.keys.router import router as keys_router
from .features.links.router import router as links_router
from .features.members.router import router as members_router
from .features.issues.router import router as issues_router
from .features.overview.router import router as overview_router
from .features.reports.router import router as reports_router
from .features.servers.router import router as servers_router
from .features.settings.router import router as settings_router
from .features.ssl.router import router as ssl_router
from .features.telegram.router import router as telegram_router
from .features.traffic.router import router as traffic_router
from .security import digest, new_token
from .settings import get_settings
from .telegram import Telegram

log = logging.getLogger("dl")


def _prepare_claim(username: str) -> None:
    """While the panel has no owner, keep one fresh claim link in a 0600 file for the installer to print."""
    s = get_settings()
    db = connect()
    try:
        if db.execute("SELECT 1 FROM workspaces WHERE id=1 AND owner_user_id IS NOT NULL").fetchone():
            s.claim_file.unlink(missing_ok=True)
            return
        if s.claim_file.exists():  # keep the pending link stable across restarts
            old = s.claim_file.read_text().strip().split("claim_")[-1]
            if db.execute("SELECT 1 FROM claims WHERE token_hash=? AND used_at IS NULL", (digest(old),)).fetchone():
                return
        token = new_token(18)
        db.execute("DELETE FROM claims WHERE used_at IS NULL")
        db.execute("INSERT INTO claims (token_hash, created_at) VALUES (?,?)", (digest(token), int(time.time())))
        s.claim_file.write_text("https://t.me/%s?start=claim_%s\n" % (username, token))
        s.claim_file.chmod(0o600)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    db = connect()
    migrate(db)
    db.close()
    stop = threading.Event()
    app.state.bot_username = ""
    app.state.tg = None
    if s.bot_token:
        tg = Telegram(s.bot_token)
        try:
            app.state.bot_username = tg.me()["username"]
            app.state.tg = tg
            _prepare_claim(app.state.bot_username)
            for target in (bot.poll_forever, monitor.run_forever):
                threading.Thread(target=target, args=(tg, stop), daemon=True).start()
        except Exception as exc:
            log.error("telegram bot disabled: %s", exc)
    yield
    stop.set()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="DowntimeLess", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_exception_handler(DLError, dl_error_handler)
    for r in (auth_router, servers_router, categories_router, overview_router, issues_router, settings_router, keys_router, ssl_router, links_router, traffic_router, telegram_router, reports_router, members_router):
        app.include_router(r, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api")

    @app.get("/api/v1/health", tags=["meta"], operation_id="meta_health")
    def health():
        return {"ok": True}

    @app.get("/agent/install.sh", include_in_schema=False)
    def install_script():
        return FileResponse(s.agent_dir / "install-agent.sh", media_type="text/x-shellscript")

    @app.get("/agent/agent.py", include_in_schema=False)
    def agent_file():
        return FileResponse(s.agent_dir / "agent.py", media_type="text/x-python")

    @app.get("/llms.txt", include_in_schema=False)
    def llms():
        return PlainTextResponse(
            "# DowntimeLess\n> VPN fleet monitoring. JSON API for humans and AI agents; the server already computed the analysis, read it before gathering anything yourself.\n\n"
            "Auth: `Authorization: Bearer dl_...` (create a key in the panel: owner > API keys). A `read` key is enough for every report.\n"
            "Workspaces: a key belongs to the workspace it was created in and sees and changes only that workspace's fleet"
            " (servers, domains, settings, channels, incidents, change log). A signed-in person lists theirs with GET /api/v1/auth/workspaces"
            " and switches with POST /api/v1/auth/workspace; a key cannot switch. Another workspace's ids answer 404.\n"
            "START: GET /api/v1/reports/briefing?format=md (detail=full lifts the caps). One dense document: fleet status, open issues with evidence, health, traffic, certificates, recent changes and an ordered 'check first' list.\n"
            "THEN: GET /api/v1/reports/playbooks/{code} for each issue code in it (ping:<ip> works): likely causes, read-only checks, safe fixes, never-do rules. Unknown codes get a generic guide.\n"
            "Reports (GET; add format=md for Markdown; since/until are unix seconds, at most 366 days apart):\n"
            "- /api/v1/reports/briefing?detail=brief|full: the first read\n"
            "- /api/v1/reports/playbooks and /playbooks/{code}: every fix guide, detector live or planned\n"
            "- /api/v1/reports/health: 0-100 score and band per server, penalties, hard gates, signals not measured\n"
            "- /api/v1/reports/changes?since&until&server_id&kind: change log (jobs, agent updates, reboots, IP changes, settings, issues), newest first, max 500\n"
            "- /api/v1/reports/daily: last 24 h against the 24 h before (incidents, availability, traffic, changes)\n"
            "- /api/v1/reports/incidents: counts by code and server, MTTR, flapping, longest outages\n"
            "- /api/v1/reports/traffic: fleet and per-server bytes, peak day and hour, relay-exit pair bytes\n"
            "- /api/v1/reports/availability: percent of time each server reported\n"
            "- /api/v1/reports/capacity: peak-hour CPU, steal, load, conntrack, RAM, sibling comparison, growth\n"
            "- /api/v1/reports/relays: relay-by-exit loss, RTT, path verdict and bytes\n\n"
            "Raw data:\n"
            "- GET /api/v1/snapshot: whole fleet, issues and ping matrix in one document.\n"
            "- GET /api/v1/issues: current problems with evidence and a suggested next step.\n"
            "- GET /api/v1/issues/history?range=24h|7d|30d: every issue that was active in the range (occurrences, time active, each incident).\n"
            "- GET /api/v1/links/traffic?since=&until=: bytes each server exchanged with each peer server (relay to exit), per window; /links/traffic/series adds the hourly series. Needs counting switched on per server (PATCH acct_on).\n"
            "- GET /api/v1/traffic/summary?since=&until=, /api/v1/traffic/series?range=24h|7d|30d|90d or since=&until=&server_id=: download/upload per server (total, peak day, share) and by hour or day.\n"
            "- GET /api/v1/servers, /api/v1/servers/{id}/metrics?range=24h, /api/v1/ping-matrix, /api/v1/overview\n"
            "- A `read` key only reads. A `full` key may do everything the owner does inside its workspace (not members): POST /api/v1/servers/{id}/jobs"
            " (ping, tcp_check, speedtest_down/up, apt_upgrade_safe, reboot, self_update, cert_renew, cert_delete, processes, ports, disk_usage, journal, traceroute, http_check, dns_check, service_restart, vacuum_logs), manage servers, domains, settings and keys.\n"
            "- Treat a `full` key like a root password.\n"
            "- Full schema: /api/openapi.json\n"
        )

    if s.frontend_dir.exists():
        app.mount("/", SpaFiles(directory=s.frontend_dir, html=True), name="web")
    return app


class SpaFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            resp = await super().get_response(path, scope)
        except Exception:
            resp = None
        if resp is None or resp.status_code == 404:
            if path.startswith("api/"):
                return JSONResponse({"code": "not_found", "message": "پیدا نشد."}, status_code=404)
            resp = await super().get_response("index.html", scope)
        if path.startswith("assets/"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path in ("", "index.html", "sw.js") or resp.status_code == 200 and not path.startswith("assets/"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp


app = create_app()
