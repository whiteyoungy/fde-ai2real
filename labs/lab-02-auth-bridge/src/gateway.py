#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""mTLS + OAuth2 认证桥接网关 —— "网关终结模式"（讲义第 10 章 10.3 节）。

对外：标准 OAuth2 资源服务器。接受 ``Authorization: Bearer <token>``，
      通过 IdP 的 ``/oauth2/introspect`` 校验 active / scope / 过期。
对内：用 mTLS 客户端证书调遗留系统。遗留系统完全不感知外部客户用的是
      OAuth2、Basic 还是别的什么协议——认证协议的转换在网关这一层
      彻底终结，不向内传导。

用法：
    python3 -m src.gateway --port 19000 \\
        --legacy https://127.0.0.1:19443 --idp http://127.0.0.1:19080

两个关键设计点（对应讲义 10.1 / 10.3 节，也是本 Lab 的验收重点）：

1. 超时预算分配（10.1 节）：外部调用方给网关的耐心是有限的。网关把这份
   预算显式切给下游各跳（IdP introspect、遗留系统 mTLS 调用），任何一跳
   超预算立刻失败并向上返回网关错误码（502/503/504），绝不原样把下游的
   慢传导给调用方。

2. 客户端证书轮换不中断请求（10.3 节）：网关对遗留系统的 mTLS 身份是
   "当前生效的证书状态对象"（ClientCertState），而不是一份写死的证书
   文件路径。轮换 = 生成新状态对象 + 原子替换指针，旧状态对象在自己
   持有的飞行请求处理完之前不会被丢弃。见 CertManager 的注释。
"""
import argparse
import json
import pathlib
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CERT_DIR_DEFAULT = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "certs"

# ── 超时预算（10.1 节：把总预算显式切给每一跳，不要囫囵吞枣）───────
# verify.sh 要求网关必须在 2500ms 内对调用方给出结果（504/502/503）。
# IdP 是本机 mock，几毫秒内必回；真正会失控的是遗留系统那一跳，所以把
# 大部分预算（1.5s）留给它，IdP 只给 1.0s 兜底，两者相加仍远小于 2.5s，
# 留出网络往返、TLS 握手、Python 解释器调度的余量。
IDP_TIMEOUT = 1.0
LEGACY_TIMEOUT = 1.5

REQUIRED_SCOPE = "orders.read"


class ClientCertState:
    """一份"网关对遗留系统的 mTLS 身份"快照：证书/私钥 + 由它们构造的
    SSLContext，外加一个"这一代证书当前有多少请求正在用它跟遗留系统
    通话"的引用计数。

    引用计数是重叠窗口能够"零中断"的关键：轮换只是让 CertManager 不再
    把这个状态对象发给*新*请求，但已经拿到它的*旧*请求会把它用完、
    close 掉连接、release 计数，全程不受影响。
    """

    def __init__(self, name: str, crt: pathlib.Path, key: pathlib.Path, ca: pathlib.Path):
        self.name = name
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(str(ca))
        ctx.load_cert_chain(str(crt), str(key))
        self.ssl_context = ctx
        self.crt_path = str(crt)
        self.created_at = time.time()
        self._lock = threading.Lock()
        self._inflight = 0

    def acquire(self):
        with self._lock:
            self._inflight += 1

    def release(self):
        with self._lock:
            self._inflight -= 1

    @property
    def inflight(self) -> int:
        with self._lock:
            return self._inflight


class CertManager:
    """持有"网关当前用哪套客户端证书跟遗留系统握手"，支持原子轮换。

    现场教训（README 里详细展开）：证书快过期了才临时去换，是来不及的——
    生成新证书、验证链路、灰度切换都需要时间。正确做法是让"下一代"证书
    提前签好、提前部署到位，在**重叠期**内新旧证书都对 CA 有效、都被
    遗留系统信任，网关随时可以原子切换过去；确认旧证书不再被任何飞行
    请求使用后，再吊销/归档旧证书。本 Lab 的 gateway-client（3 天有效）
    与 gateway-client-next（3650 天有效，同一 CA 签发）就是这个模型的
    最小复现。
    """

    NAMED = {
        "current": ("gateway-client.crt", "gateway-client.key"),
        "next": ("gateway-client-next.crt", "gateway-client-next.key"),
    }

    def __init__(self, cert_dir: pathlib.Path):
        self.cert_dir = cert_dir
        self.ca_path = cert_dir / "ca.crt"
        crt, key = self.NAMED["current"]
        self._current = ClientCertState("gateway-client:current", cert_dir / crt,
                                         cert_dir / key, self.ca_path)
        self._previous = None
        self._lock = threading.Lock()

    def get(self) -> ClientCertState:
        """新请求调用它拿"当前"状态。这一步只是读一个引用，天然线程安全
        （Python 引用赋值/读取在 GIL 下是原子的），不需要额外加锁就能保证
        "拿到的要么是旧的要么是新的，绝不会拿到一半"。"""
        with self._lock:
            return self._current

    def rotate(self, to: str = "next"):
        """切换到 ``to`` 指定的证书对。这是唯一的"写"操作：
        1. 先把新证书加载进一个全新的 SSLContext（失败就整体不生效，
           不会把网关切到一个加载失败的半成品状态）；
        2. 再原子地把 ``self._current`` 指针换过去。

        切换的瞬间之前已经在跑的请求，早已经从 ``get()`` 拿到了*旧*的
        ClientCertState 对象引用并调用了 ``acquire()``——它们跟这次
        指针替换无关，会用旧证书把自己的这次遗留系统调用走完。
        之后进来的新请求，``get()`` 拿到的就是新对象了。
        """
        if to not in self.NAMED:
            raise KeyError(to)
        crt, key = self.NAMED[to]
        new_state = ClientCertState(f"gateway-client:{to}", self.cert_dir / crt,
                                     self.cert_dir / key, self.ca_path)
        with self._lock:
            old_state = self._current
            self._current = new_state
            self._previous = old_state
        return old_state, new_state

    def drain_status(self):
        with self._lock:
            prev = self._previous
        if prev is None:
            return None
        return {"name": prev.name, "inflight": prev.inflight}


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler_cls, legacy_url: str, idp_url: str, cert_dir: pathlib.Path):
        super().__init__(addr, handler_cls)
        legacy = urllib.parse.urlsplit(legacy_url)
        if legacy.scheme != "https":
            raise SystemExit("--legacy 必须是 https://（遗留系统只认 mTLS）")
        self.legacy_host = legacy.hostname
        self.legacy_port = legacy.port or 443
        self.idp_base = idp_url.rstrip("/")
        self.certs = CertManager(cert_dir)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # 静音，避免污染 verify 输出；异常仍会打印到 stderr
        pass

    # ── 小工具 ──────────────────────────────────────────────────
    def _json(self, code: int, payload: dict, extra_headers: dict | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 调用方提前断开，不影响服务端状态

    def _unauthorized(self, reason: str):
        # 401，而不是 403：这是"你根本没证明自己是谁"，不是"你是谁我知道，
        # 但你没权限"。混淆这两者是现场常见的踩坑点。
        self._json(401, {"error": "invalid_token", "error_description": reason},
                   {"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{reason}"'})

    def _introspect(self, token: str) -> dict:
        data = urllib.parse.urlencode({"token": token}).encode()
        url = f"{self.server.idp_base}/oauth2/introspect"
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=IDP_TIMEOUT) as resp:
            return json.loads(resp.read().decode())

    # ── 路由 ────────────────────────────────────────────────────
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith("/api/orders/"):
            return self._handle_order(path.rsplit("/", 1)[-1])
        if path == "/admin/status":
            return self._handle_status()
        if path == "/healthz":
            return self._json(200, {"status": "ok"})
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path == "/admin/rotate":
            return self._handle_rotate()
        self._json(404, {"error": "not_found"})

    # ── /api/orders/{id} ───────────────────────────────────────
    def _handle_order(self, order_id: str):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not auth[len("Bearer "):].strip():
            return self._unauthorized("missing bearer token")
        token = auth[len("Bearer "):].strip()

        try:
            info = self._introspect(token)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            # IdP 自己不可用是网关的问题，不是调用方凭据的问题：503，不是 401。
            return self._json(503, {"error": "idp_unavailable", "error_description": str(e)})

        if not info.get("active"):
            return self._unauthorized("token inactive or expired")

        scopes = set((info.get("scope") or "").split())
        if REQUIRED_SCOPE not in scopes:
            return self._json(403, {"error": "insufficient_scope",
                                     "required_scope": REQUIRED_SCOPE})

        # 对内：mTLS 调遗留系统。客户端（调用这个网关的人）从头到尾
        # 不知道、也不需要知道这一步的存在。
        state = self.server.certs.get()
        state.acquire()
        try:
            conn = HTTPSConnection(self.server.legacy_host, self.server.legacy_port,
                                    context=state.ssl_context, timeout=LEGACY_TIMEOUT)
            try:
                conn.request("GET", f"/legacy/v1/orders/{order_id}")
                resp = conn.getresponse()
                raw = resp.read()
                status = resp.status
            finally:
                conn.close()
        except (socket.timeout, TimeoutError):
            # 超时预算生效的地方（10.1 节）：遗留系统慢，网关不陪它慢。
            return self._json(504, {"error": "gateway_timeout",
                                     "error_description":
                                         f"legacy did not respond within {LEGACY_TIMEOUT}s budget"})
        except (ConnectionRefusedError, ssl.SSLError, OSError) as e:
            return self._json(502, {"error": "bad_gateway", "error_description": str(e)})
        finally:
            state.release()

        if status == 404:
            return self._json(404, {"error": "order_not_found", "order_id": order_id})
        if status != 200:
            return self._json(502, {"error": "bad_gateway",
                                     "error_description": f"legacy status {status}"})

        try:
            legacy_obj = json.loads(raw.decode())
        except json.JSONDecodeError:
            return self._json(502, {"error": "bad_gateway",
                                     "error_description": "legacy returned non-JSON body"})

        # 网关顺手把遗留系统的老式大写字段翻译成现代小写 API 形状；
        # 同时保留原始报文，方便排障。字段翻译本身不是本 Lab 的重点，
        # 但这正是"网关终结模式"里网关该干的事：协议 + 形状的转换都在
        # 这一层做完，两边谁也不用迁就对方。
        payload = {
            "order_id": legacy_obj.get("ORDER_ID", order_id),
            "status": legacy_obj.get("STATUS"),
            "amount_cents": legacy_obj.get("AMOUNT_CENTS"),
            "updated_at": legacy_obj.get("UPDATED_AT"),
            "_legacy_raw": legacy_obj,
        }
        return self._json(200, payload)

    # ── /admin/rotate、/admin/status ───────────────────────────
    def _handle_rotate(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b""
        to = "next"
        if raw:
            try:
                body = json.loads(raw.decode())
                to = body.get("to", "next")
            except json.JSONDecodeError:
                pass
        try:
            old, new = self.server.certs.rotate(to)
        except KeyError:
            return self._json(400, {"error": "unknown_cert", "known": sorted(CertManager.NAMED)})
        self._json(200, {
            "rotated_to": new.name,
            "previous": old.name,
            "previous_inflight_at_switch": old.inflight,
        })

    def _handle_status(self):
        cur = self.server.certs.get()
        self._json(200, {
            "current": cur.name,
            "current_inflight": cur.inflight,
            "previous": self.server.certs.drain_status(),
        })


def main(argv=None):
    ap = argparse.ArgumentParser(description="mTLS + OAuth2 认证桥接网关")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--legacy", required=True, help="遗留系统基址，如 https://127.0.0.1:19443")
    ap.add_argument("--idp", required=True, help="IdP 基址，如 http://127.0.0.1:19080")
    ap.add_argument("--cert-dir", default=str(CERT_DIR_DEFAULT), help="客户端证书所在目录")
    a = ap.parse_args(argv)

    cert_dir = pathlib.Path(a.cert_dir)
    server = GatewayServer(("127.0.0.1", a.port), Handler, a.legacy, a.idp, cert_dir)
    print(f"[gateway] 认证桥接网关已启动 http://127.0.0.1:{a.port}  "
          f"legacy(mTLS)={a.legacy}  idp={a.idp}", flush=True)
    print(f"[gateway] 超时预算：introspect<={IDP_TIMEOUT}s legacy<={LEGACY_TIMEOUT}s "
          f"（外部预算 2.5s，见 verify.sh [6/7]）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
