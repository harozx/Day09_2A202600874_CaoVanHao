"""
Proxy server: phục vụ report.html (port 8888) + proxy A2A call đến Customer Agent (port 10100).
Chạy: uv run python proxy_server.py
Mở:   http://localhost:8888/report.html
"""

import asyncio
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

AGENT_BASE = "http://localhost:10100"
STATIC_DIR = Path(__file__).parent


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"HTTP {format % args}")

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # Proxy: /.well-known/agent.json và agent-card.json
        if path in ("/.well-known/agent.json", "/.well-known/agent-card.json"):
            try:
                req = urllib.request.urlopen(f"{AGENT_BASE}{path}", timeout=5)
                data = req.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(502)
                self._cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # Static files
        if path == "/" or path == "":
            path = "/report.html"

        file_path = STATIC_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            content_type = {
                ".html": "text/html; charset=utf-8",
                ".css":  "text/css",
                ".js":   "application/javascript",
                ".json": "application/json",
            }.get(file_path.suffix, "application/octet-stream")

            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = self.path

        # Proxy: A2A JSON-RPC call
        if path == "/a2a" or path == "/":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                req = urllib.request.Request(
                    AGENT_BASE,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=120)
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(data)
            except urllib.error.URLError as e:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Cannot reach Customer Agent: {e}"}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    port = 8888
    server = HTTPServer(("0.0.0.0", port), ProxyHandler)
    logger.info(f"Proxy server running at http://localhost:{port}/report.html")
    logger.info(f"Proxying A2A calls → {AGENT_BASE}")
    server.serve_forever()
