#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""被交付的那个服务。刻意做得极简——本 Lab 要练的是交付方式，不是服务本身。

只有一个 /healthz 端点，离线安装脚本靠它确认"服务真的起来了"。
注意它不监听 0.0.0.0 之外的任何东西，也不发出任何出站请求：
断网容器里跑得起来，是这个 Lab 的前提。
"""
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get("APP_VERSION", "1.0.0")

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_GET(self):
        body = json.dumps({"ok": True, "version": VERSION,
                           "endpoint": self.path}).encode()
        code = 200 if self.path == "/healthz" else 404
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"[app] listening on 0.0.0.0:{port} version={VERSION}", flush=True)
    try:
        ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
