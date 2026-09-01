#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""ERP 桥接层：mTLS 连接、失败分类、退避重试、熔断。

这一层是「模型侧」与「遗留系统侧」的分界线。分界线的含义是：

  - 证书路径、证书有效期、TLS 握手、重试次数、熔断阈值 —— 全在这一层以下，
    模型永远看不到，也永远不需要知道。
  - 这一层向上只暴露两件事：**这次调用成不成**，以及**值不值得再试一次**。

只用标准库 `http.client`。遗留客户的机器上常常连 pip 都出不去网，
多一个第三方依赖就多一次上线前的扯皮 —— 这是本 Lab 有意保留的取舍。
"""
from __future__ import annotations

import json
import socket
import ssl
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.client import HTTPSConnection
from pathlib import Path

# 证书默认位置。注意：这个常量只在桥接层内部使用，
# 绝不允许出现在任何工具的 description / input_schema 里。
DEFAULT_CERT_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "certs"


# ── 失败分类 ────────────────────────────────────────────────────
#
# 遗留 ERP 的失败不是一种东西。桥接层最常见的实现 bug，就是把所有非 200
# 都塞进同一个 except 里重试三遍 —— 它会把一次「这个单号不存在」的即时答复，
# 变成用户多等三倍时间才拿到的同一句话。

@dataclass(frozen=True)
class Failure:
    """一次失败的结构化描述。`retryable` 是给上层（最终是模型）看的唯一结论。"""

    code: str
    message: str
    retryable: bool
    http_status: int | None = None
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        out = {"ok": False, "error": self.code, "message": self.message,
               "retryable": self.retryable}
        if self.http_status is not None:
            out["upstream_status"] = self.http_status
        if self.detail:
            out["detail"] = self.detail
        return out


class BridgeFailure(Exception):
    """桥接层内部用的受控异常，绝不允许穿透到 MCP 工具的返回值之外。"""

    def __init__(self, failure: Failure):
        super().__init__(f"{failure.code}: {failure.message}")
        self.failure = failure


# ERP 业务性拒绝 → 重试它们是 bug。ERP 的错误码是大写下划线的内部枚举，
# 在这里一次性翻译成桥接层的小写码，模型侧不再见到 ERP 的内部词汇。
_BUSINESS_ERRORS = {
    "ORDER_NOT_FOUND": (
        "order_not_found",
        "ERP 中不存在该订单号，请与用户核对单号后重试；重复调用不会改变结果。",
    ),
    "ORDER_NOT_IN_PENDING_APPROVAL": (
        "order_not_in_pending_approval",
        "订单当前不处于待审批状态，无法审批。这是业务状态问题，重试无用。",
    ),
    "NOTE_TEXT_REQUIRED": (
        "note_text_required",
        "备注内容为空。请补全备注文本后再调用。",
    ),
    "ERP_DOES_NOT_ACCEPT_BEARER_TOKEN": (
        "upstream_auth_misconfigured",
        "ERP 拒绝 Bearer token 鉴权方式，这是桥接层配置错误，请联系维护者。",
    ),
}


def classify(status: int, payload: dict) -> Failure:
    """把 ERP 的 HTTP 响应翻译成桥接层的失败分类。

    规则（与 README「三类失败」表一致）：
      503 / 502 / 504 → 临时不可用，可重试
      404 / 409 / 400 → 业务性拒绝，**不可重试**
      其它非 2xx      → 未知，保守起见不重试，避免放大对遗留系统的压力
    """
    erp_code = str(payload.get("ERROR") or "")
    if erp_code in _BUSINESS_ERRORS:
        code, msg = _BUSINESS_ERRORS[erp_code]
        detail = {k.lower(): v for k, v in payload.items() if k != "ERROR"}
        return Failure(code, msg, retryable=False, http_status=status, detail=detail)

    if status in (502, 503, 504):
        return Failure(
            "upstream_unavailable",
            "ERP 暂时不可用（已按退避策略重试仍未成功）。稍后可重试。",
            retryable=True,
            http_status=status,
        )
    if status == 429:
        return Failure("upstream_rate_limited", "ERP 限流，稍后可重试。",
                       retryable=True, http_status=status)
    return Failure(
        "upstream_error",
        f"ERP 返回了未预期的状态码 {status}（{erp_code or '无错误码'}）。重试大概率无效。",
        retryable=False,
        http_status=status,
    )


# ── 熔断 ────────────────────────────────────────────────────────

class CircuitBreaker:
    """极简熔断器：连续 N 次可重试失败后打开，打开期间**不再向下游发任何请求**。

    「熔断」的意义就是不打下游。只记个状态却照旧发请求，那叫日志，不叫熔断。
    """

    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

    def __init__(self, threshold: int = 3, recovery_seconds: float = 30.0):
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._state = self.CLOSED

    @property
    def state(self) -> str:
        with self._lock:
            return self._peek_state()

    def _peek_state(self) -> str:
        if self._state == self.OPEN and \
                time.monotonic() - self._opened_at >= self.recovery_seconds:
            self._state = self.HALF_OPEN
        return self._state

    def allow(self) -> bool:
        """返回 False 表示应当立即短路，一个字节都不许发给下游。"""
        with self._lock:
            return self._peek_state() != self.OPEN

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._state = self.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == self.HALF_OPEN or \
                    self._consecutive_failures >= self.threshold:
                self._state = self.OPEN
                self._opened_at = time.monotonic()

    def open_failure(self) -> Failure:
        return Failure(
            "circuit_open",
            "桥接层已对 ERP 熔断（连续失败过多），当前不会再向 ERP 发起请求。"
            f"约 {int(self.recovery_seconds)} 秒后自动尝试恢复，请稍后再试或改走人工流程。",
            retryable=False,
        )


# ── ERP 客户端 ──────────────────────────────────────────────────

class ErpClient:
    """只认 mTLS 客户端证书的遗留 ERP 的访问器。

    超时预算的两条规矩：
      1. **503 才重试。** 退避 + 抖动，最多 `max_attempts` 次。
      2. **超时不在层内重试。** 一次超时说明下游已经慢到不可用，
         再等两轮只会把 5 秒变成 15 秒，让整个 Agent 会话卡死。
         快速失败并把 `retryable=true` 交给上层，让人/模型决定要不要再来一次。
    """

    def __init__(
        self,
        base_url: str,
        cert_dir: Path | str = DEFAULT_CERT_DIR,
        timeout: float = 2.0,
        max_attempts: int = 3,
        backoff_base: float = 0.1,
        breaker: CircuitBreaker | None = None,
    ):
        parsed = urllib.parse.urlsplit(base_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 443
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.breaker = breaker if breaker is not None else CircuitBreaker()
        self.cert_dir = Path(cert_dir)
        self._ctx = self._build_ssl_context()

    # -- TLS ------------------------------------------------------
    def _build_ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=str(self.cert_dir / "ca.crt"))
        ctx.load_cert_chain(str(self.cert_dir / "bridge-client.crt"),
                            str(self.cert_dir / "bridge-client.key"))
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx

    # -- 单次请求 --------------------------------------------------
    def _once(self, method: str, path: str, body: dict | None, timeout: float
              ) -> tuple[int, dict]:
        conn = HTTPSConnection(self.host, self.port, context=self._ctx,
                               timeout=timeout)
        try:
            payload = json.dumps(body).encode() if body is not None else None
            headers = {"Accept": "application/json"}
            if payload is not None:
                headers["Content-Type"] = "application/json"
                headers["Content-Length"] = str(len(payload))
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            try:
                data = json.loads(raw.decode() or "{}")
            except (ValueError, UnicodeDecodeError):
                data = {"ERROR": "ERP_RETURNED_NON_JSON",
                        "RAW": raw[:200].decode("utf-8", "replace")}
            return resp.status, data
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # -- 带重试与熔断的调用 ----------------------------------------
    def call(self, method: str, path: str, body: dict | None = None,
             timeout: float | None = None) -> dict:
        """成功返回 ERP 的 JSON；失败抛 `BridgeFailure`（由工具层翻成结构化返回）。"""
        budget = timeout if timeout is not None else self.timeout
        last: Failure | None = None

        for attempt in range(1, self.max_attempts + 1):
            # 熔断检查放在**发请求之前**，且每次重试前都查一遍：
            # 否则一次操作的三轮重试会在熔断打开后继续捅下游。
            if not self.breaker.allow():
                raise BridgeFailure(self.breaker.open_failure())

            try:
                status, data = self._once(method, path, body, budget)
            except (socket.timeout, TimeoutError):
                # 超时：快速失败，不在层内重试（见类 docstring 规矩 2）
                self.breaker.record_failure()
                raise BridgeFailure(Failure(
                    "upstream_timeout",
                    f"ERP 在 {budget:g} 秒预算内未响应，本次调用已放弃。"
                    "这通常是下游临时变慢，可稍后重试。",
                    retryable=True,
                ))
            except (ssl.SSLError, OSError) as exc:
                self.breaker.record_failure()
                raise BridgeFailure(Failure(
                    "upstream_unreachable",
                    f"无法与 ERP 建立连接：{type(exc).__name__}。请联系桥接层维护者。",
                    retryable=True,
                ))

            if 200 <= status < 300:
                self.breaker.record_success()
                return data

            last = classify(status, data)
            if not last.retryable:
                # 业务性拒绝不算下游故障，不该把熔断器往阈值上推。
                self.breaker.record_success()
                raise BridgeFailure(last)

            if attempt < self.max_attempts:
                time.sleep(self.backoff_base * (2 ** (attempt - 1)))

        self.breaker.record_failure()
        assert last is not None
        raise BridgeFailure(last)

    # -- 业务方法 --------------------------------------------------
    def get_order(self, order_id: str, timeout: float | None = None) -> dict:
        return self.call("GET", f"/erp/v2/orders/{urllib.parse.quote(order_id)}",
                         timeout=timeout)

    def add_note(self, order_id: str, text: str, timeout: float | None = None) -> dict:
        return self.call("POST",
                         f"/erp/v2/orders/{urllib.parse.quote(order_id)}/notes",
                         {"text": text}, timeout=timeout)

    def approve(self, order_id: str, timeout: float | None = None) -> dict:
        return self.call("POST",
                         f"/erp/v2/orders/{urllib.parse.quote(order_id)}/approve",
                         {}, timeout=timeout)

    def stats(self) -> dict:
        """读 ERP 自己的调用统计。仅供验收探针使用，业务路径不碰它。"""
        status, data = self._once("GET", "/erp/v2/_stats", None, 5.0)
        return data if status == 200 else {}
