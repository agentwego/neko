#!/usr/bin/env python3
import os
import socket
import threading

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = int(os.environ.get("CLOAKBROWSER_PROXY_PORT", "9223"))
TARGET_HOST = "127.0.0.1"
TARGET_PORT = int(os.environ.get("CLOAKBROWSER_CDP_PORT", "9222"))


def pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def handle_client(client_sock):
    upstream = socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=10)
    threading.Thread(target=pipe, args=(client_sock, upstream), daemon=True).start()
    threading.Thread(target=pipe, args=(upstream, client_sock), daemon=True).start()


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((LISTEN_HOST, LISTEN_PORT))
        server.listen(128)
        print(f"cdp proxy listening on {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}", flush=True)
        while True:
            client_sock, _ = server.accept()
            threading.Thread(target=handle_client, args=(client_sock,), daemon=True).start()


if __name__ == "__main__":
    main()
