#!/usr/bin/env python3
"""Small HTTP/HTTPS proxy that adds Basic auth to an upstream HTTP proxy.

Chromium is launched against this local unauthenticated proxy because browser
proxy credentials in command-line flags are unreliable. The forwarder injects
Proxy-Authorization when connecting to the configured upstream proxy.
"""

import base64
import os
import select
import socket
import socketserver
import threading

LISTEN_HOST = os.environ.get("CLOAKBROWSER_LOCAL_PROXY_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("CLOAKBROWSER_LOCAL_PROXY_PORT", "18080"))
UPSTREAM = os.environ["CLOAKBROWSER_PROXY_SERVER"]
USERNAME = os.environ["CLOAKBROWSER_PROXY_USERNAME"]
PASSWORD = os.environ["CLOAKBROWSER_PROXY_PASSWORD"]

if ":" not in UPSTREAM:
    raise SystemExit("CLOAKBROWSER_PROXY_SERVER must be host:port")
UPSTREAM_HOST, UPSTREAM_PORT_RAW = UPSTREAM.rsplit(":", 1)
UPSTREAM_PORT = int(UPSTREAM_PORT_RAW)
AUTH = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()


def recv_until(sock: socket.socket, marker: bytes = b"\r\n\r\n", limit: int = 1024 * 1024) -> bytes:
    data = b""
    while marker not in data:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
        if len(data) > limit:
            raise OSError("request headers too large")
    return data


def inject_proxy_auth(header: bytes) -> bytes:
    head, sep, rest = header.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    filtered = [line for line in lines if not line.lower().startswith(b"proxy-authorization:")]
    filtered.append(f"Proxy-Authorization: Basic {AUTH}".encode())
    return b"\r\n".join(filtered) + sep + rest


def relay(a: socket.socket, b: socket.socket) -> None:
    sockets = [a, b]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 300)
            if not readable:
                break
            for src in readable:
                dst = b if src is a else a
                data = src.recv(65536)
                if not data:
                    return
                dst.sendall(data)
    finally:
        for s in sockets:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        client = self.request
        upstream = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT), timeout=30)
        first = recv_until(client)
        if not first:
            upstream.close()
            return
        upstream.sendall(inject_proxy_auth(first))
        relay(client, upstream)


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadingServer((LISTEN_HOST, LISTEN_PORT), Handler) as server:
        print(
            f"proxy auth forwarder listening on {LISTEN_HOST}:{LISTEN_PORT} -> {UPSTREAM_HOST}:{UPSTREAM_PORT}",
            flush=True,
        )
        server.serve_forever()
