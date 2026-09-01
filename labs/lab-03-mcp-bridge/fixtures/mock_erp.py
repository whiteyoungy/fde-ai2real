#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""模拟只认 mTLS 的遗留 ERP 系统，带故障注入。

这是 Lab-03 的被封装对象。保留了遗留 ERP 的典型特征：
- 只认客户端证书，不认任何 token（模型侧的凭据在这里一文不值）
- 字段名大写下划线，状态是内部枚举（SHIPPED / PENDING_APPROVAL / ...）
- 审批接口有前置状态要求，状态不对直接拒（不是所有失败都值得重试）

故障注入（供验收脚本驱动，业务代码不该知道它的存在）：
  POST /erp/v2/_fault  {"mode":"flaky","count":2}   接下来 2 次业务调用返回 503
  POST /erp/v2/_fault  {"mode":"timeout","sleep":5} 业务调用睡 5 秒
  POST /erp/v2/_fault  {"mode":"off"}               恢复正常
  GET  /erp/v2/_stats                               各端点的实际请求次数

_fault 与 _stats 自身不计入统计、也不受故障影响——否则清不掉故障，
统计数字也会被自己污染。

用法：python3 fixtures/mock_erp.py [--port 19543]
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

ORDERS = {
    "ORD-20260317-001": {"ORDER_ID": "ORD-20260317-001", "STATUS": "SHIPPED",
                         "AMOUNT_CENTS": 128000, "TRACKING_NO": "SF1234567890",
                         "ETA": "2026-03-20", "NOTES": []},
    "ORD-20260317-002": {"ORDER_ID": "ORD-20260317-002", "STATUS": "PENDING_APPROVAL",
                         "AMOUNT_CENTS": 4500, "TRACKING_NO": None,
                         "ETA": None, "NOTES": []},
    "ORD-20260317-003": {"ORDER_ID": "ORD-20260317-003", "STATUS": "DELIVERED",
                         "AMOUNT_CENTS": 76000, "TRACKING_NO": "JD9988776655",
                         "ETA": "2026-03-15", "NOTES": []},
}

_lock = threading.Lock()
_fault = {"mode": "off", "count": 0, "sleep": 0.0}
_stats = {"query": 0, "note": 0, "approve": 0, "total": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
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

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except Exception:
            return {}

    def _apply_fault(self):
        """返回 True 表示本次调用已被故障拦截（响应已发出）。"""
        with _lock:
            mode, cnt, slp = _fault["mode"], _fault["count"], _fault["sleep"]
            if mode == "flaky" and cnt > 0:
                _fault["count"] = cnt - 1
                hit = True
            else:
                hit = False
        if hit:
            self._json(503, {"ERROR": "ERP_TEMPORARILY_UNAVAILABLE"})
            return True
        if mode == "timeout":
            time.sleep(slp)
        return False

    def _count(self, kind):
        with _lock:
            _stats[kind] += 1
            _stats["total"] += 1

    # ── GET ────────────────────────────────────────────────────
    def do_GET(self):
        if self.headers.get("Authorization", "").startswith("Bearer "):
            return self._json(400, {"ERROR": "ERP_DOES_NOT_ACCEPT_BEARER_TOKEN"})

        if self.path == "/erp/v2/_stats":
            with _lock:
                return self._json(200, {**_stats, "fault": dict(_fault)})

        if self.path.startswith("/erp/v2/orders/"):
            oid = self.path.rsplit("/", 1)[-1]
            self._count("query")
            if self._apply_fault():
                return
            row = ORDERS.get(oid)
            if not row:
                return self._json(404, {"ERROR": "ORDER_NOT_FOUND", "ORDER_ID": oid})
            return self._json(200, {**row, "SERVED_TO_CN": self._peer_cn()})

        self._json(404, {"ERROR": "NO_SUCH_ENDPOINT"})

    # ── POST ───────────────────────────────────────────────────
    def do_POST(self):
        if self.headers.get("Authorization", "").startswith("Bearer "):
            return self._json(400, {"ERROR": "ERP_DOES_NOT_ACCEPT_BEARER_TOKEN"})

        if self.path == "/erp/v2/_fault":
            b = self._body()
            with _lock:
                _fault["mode"] = b.get("mode", "off")
                _fault["count"] = int(b.get("count", 0))
                _fault["sleep"] = float(b.get("sleep", 0.0))
                if b.get("reset_stats"):
                    for k in _stats:
                        _stats[k] = 0
                return self._json(200, {"fault": dict(_fault), "stats": dict(_stats)})

        parts = self.path.strip("/").split("/")
        # /erp/v2/orders/{id}/{action}
        if len(parts) == 5 and parts[:3] == ["erp", "v2", "orders"]:
            oid, action = parts[3], parts[4]

            if action == "notes":
                self._count("note")
                if self._apply_fault():
                    return
                row = ORDERS.get(oid)
                if not row:
                    return self._json(404, {"ERROR": "ORDER_NOT_FOUND", "ORDER_ID": oid})
                text = (self._body().get("text") or "").strip()
                if not text:
                    return self._json(400, {"ERROR": "NOTE_TEXT_REQUIRED"})
                row["NOTES"].append({"TEXT": text, "BY_CN": self._peer_cn()})
                return self._json(200, {"ORDER_ID": oid, "NOTE_COUNT": len(row["NOTES"])})

            if action == "approve":
                self._count("approve")
                if self._apply_fault():
                    return
                row = ORDERS.get(oid)
                if not row:
                    return self._json(404, {"ERROR": "ORDER_NOT_FOUND", "ORDER_ID": oid})
                # 状态不对是业务性拒绝，重试多少次都不会变——桥接层要能区分
                if row["STATUS"] != "PENDING_APPROVAL":
                    return self._json(409, {"ERROR": "ORDER_NOT_IN_PENDING_APPROVAL",
                                            "CURRENT_STATUS": row["STATUS"]})
                row["STATUS"] = "APPROVED"
                return self._json(200, {"ORDER_ID": oid, "STATUS": "APPROVED",
                                        "APPROVED_BY_CN": self._peer_cn()})

        self._json(404, {"ERROR": "NO_SUCH_ENDPOINT"})


def serve(port: int):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERTS / "erp-server.crt", CERTS / "erp-server.key")
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(CERTS / "ca.crt")

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"[erp] mTLS ERP 已启动 https://127.0.0.1:{port} (仅接受 FDE-Lab Root CA 客户端证书)",
          flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=19543)
    a = ap.parse_args()
    try:
        serve(a.port)
    except KeyboardInterrupt:
        sys.exit(0)
