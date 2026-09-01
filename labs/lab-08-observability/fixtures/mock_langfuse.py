#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""本地 mock Langfuse 摄取端，替代自托管的 ClickHouse 全家桶。

第 13 章 13.5 节说得很清楚：自托管 Langfuse 要 Postgres + ClickHouse + Redis + MinIO
四个有状态服务，官方最低建议 4 vCPU / 16GiB RAM / 100GiB 存储；如果只是要验证
「埋点能不能跑通」，本地 mock 比自建一套 ClickHouse 集群划算得多。这个文件就是那个 mock。

它做三件事：
- 在 Langfuse SDK v4 实际使用的 OTLP 端点 /api/public/otel/v1/traces 上收 protobuf
- 用 opentelemetry.proto 解出 span（SDK 自带这个依赖，不用额外装）
- 把解出来的 span 以 JSON 暴露在 /_spans，供 verify.sh 断言

关键点：**/_raw 保留原始上报字节**。脱敏有没有真正生效，只能在原始字节上验——
如果只看解码后的字段，一个把 PII 塞进未被解析字段里的实现会蒙混过关。

用法：python3 fixtures/mock_langfuse.py [--port 13000]
  GET  /_spans   已收到的 span（JSON 数组）
  GET  /_raw     原始上报负载的十六进制拼接（供脱敏检测）
  POST /_reset   清空
"""
import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from opentelemetry.proto.trace.v1.trace_pb2 import TracesData
except ImportError:
    print("需要 opentelemetry-proto（langfuse SDK 的依赖）。先 pip install -r requirements.txt",
          file=sys.stderr)
    raise

_lock = threading.Lock()
_spans: list[dict] = []
_raw: list[bytes] = []


def _attr_value(v):
    """OTLP 的 AnyValue 是 oneof，取出实际值。"""
    for f in ("string_value", "bool_value", "int_value", "double_value"):
        if v.HasField(f):
            return getattr(v, f)
    if v.HasField("array_value"):
        return [_attr_value(x) for x in v.array_value.values]
    return None


def _decode(body: bytes) -> list[dict]:
    td = TracesData()
    td.ParseFromString(body)
    out = []
    for rs in td.resource_spans:
        for ss in rs.scope_spans:
            for sp in ss.spans:
                out.append({
                    "name": sp.name,
                    "trace_id": sp.trace_id.hex(),
                    "span_id": sp.span_id.hex(),
                    "parent_span_id": sp.parent_span_id.hex() or None,
                    "start_ns": sp.start_time_unix_nano,
                    "end_ns": sp.end_time_unix_nano,
                    "attributes": {kv.key: _attr_value(kv.value) for kv in sp.attributes},
                })
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/_spans":
            with _lock:
                return self._json(200, _spans)
        if self.path == "/_raw":
            with _lock:
                return self._json(200, {"payloads": len(_raw),
                                        "hex": b"".join(_raw).hex()})
        if self.path == "/_health":
            return self._json(200, {"ok": True})
        # SDK 启动时可能探测其它端点，一律 200，别让它以为服务挂了
        self._json(200, {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n) if n else b""

        if self.path == "/_reset":
            with _lock:
                _spans.clear()
                _raw.clear()
            return self._json(200, {"reset": True})

        if self.path.endswith("/otel/v1/traces"):
            try:
                decoded = _decode(body)
            except Exception as exc:                      # noqa: BLE001
                # 解不出来也要收下并记原始字节，否则 verify 只能看到"没收到"，
                # 分不清是没上报还是格式变了
                with _lock:
                    _raw.append(body)
                return self._json(200, {"decoded": 0, "error": str(exc)[:120]})
            with _lock:
                _spans.extend(decoded)
                _raw.append(body)
            return self._json(200, {"decoded": len(decoded)})

        self._json(200, {})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=13000)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"[mock-langfuse] 摄取端已启动 http://127.0.0.1:{a.port}"
          f"  (OTLP: /api/public/otel/v1/traces)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
