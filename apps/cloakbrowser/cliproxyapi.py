#!/usr/bin/env python3
"""Small OpenAI-compatible proxy API for each Neko/CloakBrowser container.

It forwards /v1/* requests to OPENAI_BASE_URL/CLIPROXY_UPSTREAM_BASE_URL and can
send upstream traffic through the same per-container browser proxy credentials.
"""
from __future__ import annotations

import base64
import json
import os
import socketserver
import sys
import traceback
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler
from typing import Dict, Iterable, Tuple

LISTEN_HOST = os.environ.get("CLIPROXY_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("CLIPROXY_PORT", "8932"))
UPSTREAM_BASE_URL = (os.environ.get("CLIPROXY_UPSTREAM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
UPSTREAM_API_KEY = os.environ.get("CLIPROXY_UPSTREAM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
LOCAL_API_KEY = os.environ.get("CLIPROXY_API_KEY", "")
PROXY_SERVER = os.environ.get("CLIPROXY_PROXY_SERVER") or os.environ.get("CLOAKBROWSER_PROXY_SERVER") or ""
PROXY_USERNAME = os.environ.get("CLIPROXY_PROXY_USERNAME") or os.environ.get("CLOAKBROWSER_PROXY_USERNAME") or ""
PROXY_PASSWORD = os.environ.get("CLIPROXY_PROXY_PASSWORD") or os.environ.get("CLOAKBROWSER_PROXY_PASSWORD") or ""
IPINFO_URL = os.environ.get("CLIPROXY_IPINFO_URL", "http://ipinfo.talordata.com")
MAX_BODY_BYTES = int(os.environ.get("CLIPROXY_MAX_BODY_BYTES", str(32 * 1024 * 1024)))
REQUEST_TIMEOUT = float(os.environ.get("CLIPROXY_REQUEST_TIMEOUT", "180"))

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:4]}...[REDACTED]"


def make_proxy_handler() -> urllib.request.ProxyHandler:
    if not PROXY_SERVER:
        return urllib.request.ProxyHandler({})
    proxy_url = PROXY_SERVER if "://" in PROXY_SERVER else f"http://{PROXY_SERVER}"
    parsed = urllib.parse.urlsplit(proxy_url)
    netloc = parsed.netloc
    if PROXY_USERNAME or PROXY_PASSWORD:
        user = urllib.parse.quote(PROXY_USERNAME, safe="")
        password = urllib.parse.quote(PROXY_PASSWORD, safe="")
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        netloc = f"{user}:{password}@{host}"
    rebuilt = urllib.parse.urlunsplit((parsed.scheme or "http", netloc, parsed.path, parsed.query, parsed.fragment))
    return urllib.request.ProxyHandler({"http": rebuilt, "https": rebuilt})


OPENER = urllib.request.build_opener(make_proxy_handler())


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    server_version = "neko-cliproxyapi/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stdout.write(json.dumps({"service": "neko-cliproxyapi", "client": self.client_address[0], "message": fmt % args}, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def send_json(self, status: int, payload: object) -> None:
        raw = json_bytes(payload)
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def check_local_auth(self) -> bool:
        if not LOCAL_API_KEY:
            return True
        return self.headers.get("authorization", "") == f"Bearer {LOCAL_API_KEY}"

    def read_body(self) -> bytes:
        length = int(self.headers.get("content-length") or "0")
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        return self.rfile.read(length) if length else b""

    def copy_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for key, value in self.headers.items():
            if key.lower() not in HOP_BY_HOP:
                headers[key] = value
        if UPSTREAM_API_KEY:
            headers["authorization"] = f"Bearer {UPSTREAM_API_KEY}"
        return headers

    def proxy_to(self, target_url: str, body: bytes | None = None) -> None:
        req = urllib.request.Request(
            target_url,
            data=body,
            headers=self.copy_headers(),
            method=self.command,
        )
        try:
            with OPENER.open(req, timeout=REQUEST_TIMEOUT) as upstream:
                self.send_response(upstream.status)
                for key, value in upstream.headers.items():
                    if key.lower() not in HOP_BY_HOP:
                        self.send_header(key, value)
                self.end_headers()
                while True:
                    chunk = upstream.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() not in HOP_BY_HOP:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(exc.read())

    def do_GET(self) -> None:  # noqa: N802
        self.route()

    def do_POST(self) -> None:  # noqa: N802
        self.route()

    def do_PUT(self) -> None:  # noqa: N802
        self.route()

    def do_PATCH(self) -> None:  # noqa: N802
        self.route()

    def do_DELETE(self) -> None:  # noqa: N802
        self.route()

    def route(self) -> None:
        try:
            parsed = urllib.parse.urlsplit(self.path)
            if self.command == "GET" and parsed.path in {"/health", "/v1/health"}:
                self.send_json(200, {
                    "ok": True,
                    "service": "neko-cliproxyapi",
                    "upstream_base_url": UPSTREAM_BASE_URL,
                    "upstream_api_key": redact(UPSTREAM_API_KEY),
                    "local_api_key": "[configured]" if LOCAL_API_KEY else "[disabled]",
                    "proxy_configured": bool(PROXY_SERVER),
                    "proxy_username": redact(PROXY_USERNAME),
                })
                return
            if self.command == "GET" and parsed.path == "/v1/ipinfo":
                req = urllib.request.Request(IPINFO_URL, method="GET")
                with OPENER.open(req, timeout=REQUEST_TIMEOUT) as upstream:
                    data = upstream.read()
                    self.send_response(upstream.status)
                    self.send_header("content-type", upstream.headers.get("content-type", "application/json; charset=utf-8"))
                    self.send_header("content-length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                return
            if not parsed.path.startswith("/v1/"):
                self.send_json(404, {"error": {"message": "not found", "type": "not_found"}})
                return
            if not self.check_local_auth():
                self.send_json(401, {"error": {"message": "invalid local CLIPROXY_API_KEY", "type": "unauthorized"}})
                return
            body = None if self.command in {"GET", "HEAD"} else self.read_body()
            target_url = f"{UPSTREAM_BASE_URL}{parsed.path}{('?' + parsed.query) if parsed.query else ''}"
            self.proxy_to(target_url, body=body)
        except ValueError as exc:
            self.send_json(413, {"error": {"message": str(exc), "type": "request_error"}})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            if not self.wfile.closed:
                self.send_json(502, {"error": {"message": str(exc), "type": "cliproxyapi_error"}})


def main() -> None:
    print(json.dumps({
        "service": "neko-cliproxyapi",
        "listen": f"{LISTEN_HOST}:{LISTEN_PORT}",
        "upstream_base_url": UPSTREAM_BASE_URL,
        "upstream_api_key": redact(UPSTREAM_API_KEY),
        "local_api_key": "[configured]" if LOCAL_API_KEY else "[disabled]",
        "proxy_configured": bool(PROXY_SERVER),
        "proxy_username": redact(PROXY_USERNAME),
    }, ensure_ascii=False), flush=True)
    with ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
