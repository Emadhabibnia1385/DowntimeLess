import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AGENT_KEY = "k-123"
DEFAULT_RESPONSE = {"interval_s": 30, "ping_targets": [], "jobs": []}


class FakeMaster:
    """Speaks the agent contract from docs/ARCHITECTURE.md and records what it receives."""

    def __init__(self):
        self.enrolls = []
        self.reports = []  # (headers, body)
        self.responses = []  # queued report responses, consumed in order
        self.agent_source = b""
        self.uploaded = 0
        self.requests = []
        master = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_GET(self):
                master.requests.append(self.path)
                if self.path == "/agent/agent.py":
                    self.reply(200, master.agent_source, "text/x-python")
                elif self.path == "/down":
                    self.reply(200, bytes(300000), "application/octet-stream")
                else:
                    self.reply(404, {"code": "not_found"})

            def do_POST(self):
                master.requests.append(self.path)
                raw = self.body()
                if self.path == "/api/agent/v1/enroll":
                    master.enrolls.append(json.loads(raw))
                    self.reply(200, {"agent_key": AGENT_KEY})
                elif self.path == "/api/agent/v1/report":
                    if self.headers.get("X-Agent-Key") != AGENT_KEY:
                        return self.reply(401, {"code": "unauthorized", "message": "no"})
                    master.reports.append((dict(self.headers), json.loads(raw)))
                    self.reply(200, master.responses.pop(0) if master.responses else DEFAULT_RESPONSE)
                elif self.path == "/up":
                    master.uploaded += len(raw)
                    self.reply(200, b"ok", "text/plain")
                else:
                    self.reply(404, {"code": "not_found"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        threading.Thread(target=self.server.serve_forever, args=(0.02,), daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
