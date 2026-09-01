#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""模拟只认 mTLS 的遗留系统。

现场里这类系统的典型特征，这里都保留了：
- 只信任特定 CA 签发的客户端证书，别的 CA 一律握手阶段就拒
- 不认 OAuth2、不认 Bearer token，只认证书里的 CN 做身份
- 接口风格老旧（路径带版本号、返回大写字段名）
- 偶发慢响应，逼调用方设超时预算

用法：python3 fixtures/mock_legacy.py [--port 9443]
"""
import argparse
import json
import pathlib
import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CERTS = pathlib.Path(__file__).parent / "certs"

# 遗留系统里的"订单"数据，字段名故意用大写下划线，像老系统
ORDERS = {
    "A-7781": {"ORDER_ID": "A-7781", "STATUS": "SHIPPED", "AMOUNT_CENTS": 128000,
               "UPDATED_AT": "2026-08-01T09:12:00Z"},
    "A-7782": {"ORDER_ID": "A-7782", "STATUS": "PENDING_REVIEW", "AMOUNT_CENTS": 4500,
               "UPDATED_AT": "2026-08-03T14:40:00Z"},
    "A-9001": {"ORDER_ID": "A-9001", "STATUS": "CANCELLED", "AMOUNT_CENTS": 0,
               "UPDATED_AT": "2026-07-19T22:05:00Z"},
}

_hits = {"total": 0, "by_cn": {}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # 静音，避免污染 verify 输出
        pass

    def _peer_cn(self):
        cert = self.connection.getpeercert()
        if not cert:
            return None
        for rdn in cert.get("subject", ()):
            for k, v in rdn:
                if k == "commonName":
                    return v
        return None

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        cn = self._peer_cn()
        _hits["total"] += 1
        _hits["by_cn"][cn or "<none>"] = _hits["by_cn"].get(cn or "<none>", 0) + 1

        # 遗留系统不认 Bearer token，只认证书 CN
        if self.headers.get("Authorization", "").startswith("Bearer "):
            return self._json(400, {"ERROR": "LEGACY_DOES_NOT_ACCEPT_BEARER_TOKEN"})

        if self.path == "/legacy/v1/_stats":
            return self._json(200, _hits)

        if self.path.startswith("/legacy/v1/orders/"):
            oid = self.path.rsplit("/", 1)[-1]
            # A-9001 故意慢，用来验调用方有没有设超时
            if oid == "A-9001":
                time.sleep(3.0)
            row = ORDERS.get(oid)
            if not row:
                return self._json(404, {"ERROR": "ORDER_NOT_FOUND", "ORDER_ID": oid})
            return self._json(200, {**row, "SERVED_TO_CN": cn})

        self._json(404, {"ERROR": "NO_SUCH_ENDPOINT"})


def serve(port: int):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERTS / "legacy-server.crt", CERTS / "legacy-server.key")
    # 关键：强制校验客户端证书，且只信任本 Lab 的根 CA
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(CERTS / "ca.crt")

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"[legacy] mTLS 服务已启动 https://127.0.0.1:{port}  (仅接受 FDE-Lab Root CA 签发的客户端证书)",
          flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9443)
    a = ap.parse_args()
    try:
        serve(a.port)
    except KeyboardInterrupt:
        sys.exit(0)
