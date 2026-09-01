#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""验收探针 CLI：驱动 MCP Server 走完 verify.sh 要看的五种场景。

    python3 -m src.check_tools --mode {dump,invoke,retry,degrade,breaker} --erp <URL>

用进程内 `Client` 直连 `MCPServer` 对象，不起子进程、不配传输层。
好处是探针看到的东西和真实 host 看到的完全一致（同一套 list_tools / call_tool
协议对象），坏处是换成 stdio / Streamable HTTP 传输后这个文件要重写。

注意 `dump` 模式必须输出**纯 JSON**：verify.sh 直接把 stdout 喂给 json.load，
多打一行日志就全盘皆输。所以本文件里所有诊断信息一律走 stderr。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

from mcp import Client

from .bridge import CircuitBreaker, ErpClient
from .server import build_server

QUERY_ORDER = "ORD-20260317-001"     # SHIPPED，只读场景
PENDING_ORDER = "ORD-20260317-002"   # PENDING_APPROVAL，审批场景


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


async def _call(client: Client, name: str, args: dict) -> tuple[dict, bool]:
    """返回 (结构化结果, 是否被 MCP 判为错误)。

    字段名是 `is_error` 不是规范文档里的 `isError`。写错不会报错——
    `getattr(res, "isError", False)` 永远返回 False，会把工具报错当成功往下传。
    这里直接取属性，写错就 AttributeError，响亮地失败。
    """
    res = await client.call_tool(name, args)
    body = res.structured_content
    if isinstance(body, dict) and set(body.keys()) == {"result"}:
        body = body["result"]        # 标量返回会被 SDK 包一层
    if body is None:
        # 两种情况会走到这里：
        #  1) 工具没有 output_schema（返回标注写成裸 dict 时 SDK 不生成 schema），
        #     结果只以 JSON 文本落在 content 里；
        #  2) 入参校验失败，structured_content 为空、原因在 content[0].text。
        texts = [getattr(c, "text", "") for c in (res.content or [])]
        joined = "\n".join(t for t in texts if t)
        try:
            parsed = json.loads(joined)
        except ValueError:
            parsed = None
        body = parsed if isinstance(parsed, dict) else {
            "ok": False, "error": "tool_input_rejected", "message": joined}
    return body, res.is_error


def _make(erp_url: str, *, threshold: int = 3) -> tuple[ErpClient, object]:
    erp = ErpClient(erp_url, breaker=CircuitBreaker(threshold=threshold,
                                                    recovery_seconds=30.0))
    return erp, build_server(erp_url, client=erp)


# ── dump：把工具表原样倒出来供验收脚本断言 ────────────────────────
async def mode_dump(erp_url: str) -> int:
    _, srv = _make(erp_url)
    async with Client(srv) as c:
        listed = await c.list_tools()
        # 属性是 input_schema，不是规范文档里的 inputSchema
        out = [{"name": t.name, "description": t.description,
                "input_schema": t.input_schema} for t in listed.tools]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


# ── invoke：三个工具各真打一次 mTLS ERP ──────────────────────────
async def mode_invoke(erp_url: str) -> int:
    erp, srv = _make(erp_url)
    marks = {}
    async with Client(srv) as c:
        q, q_err = await _call(c, "get_order_status", {"order_id": QUERY_ORDER})
        marks["query"] = "OK" if (q.get("ok") and not q_err) else f"FAIL:{q.get('error')}"

        n, n_err = await _call(c, "add_order_note",
                               {"order_id": QUERY_ORDER,
                                "text": "桥接层连通性自检，可忽略。"})
        marks["note"] = "OK" if (n.get("ok") and not n_err) else f"FAIL:{n.get('error')}"

        a, a_err = await _call(c, "approve_order", {"order_id": PENDING_ORDER})
        marks["approve"] = "OK" if (a.get("ok") and not a_err) else f"FAIL:{a.get('error')}"

    # 证书身份是**桥接层的事实**，不是模型该知道的事，所以它不在任何工具的返回值里。
    # 探针站在边界以下，可以直接问 ERP「你看到的对端是谁」。
    raw = erp.get_order(QUERY_ORDER)
    cn = raw.get("SERVED_TO_CN") or "unknown"

    print(f"query={marks['query']} note={marks['note']} "
          f"approve={marks['approve']} cn={cn}")
    return 0 if all(v == "OK" for v in marks.values()) else 1


# ── retry：注入 2 次 503，工具应重试到成功 ───────────────────────
async def mode_retry(erp_url: str) -> int:
    erp, srv = _make(erp_url)
    async with Client(srv) as c:
        body, is_err = await _call(c, "get_order_status", {"order_id": QUERY_ORDER})
    # 次数从 ERP 自己的统计里读，不是桥接层自己数的——
    # 自己数的数字证明不了请求真的发出去了。
    attempts = int(erp.stats().get("total", 0))
    result = "ok" if (body.get("ok") and not is_err) else f"fail:{body.get('error')}"
    print(f"result={result} erp_attempts={attempts}")
    return 0 if result == "ok" else 1


# ── degrade：ERP 睡 5 秒，工具须在预算内返回结构化错误 ───────────
async def mode_degrade(erp_url: str) -> int:
    _, srv = _make(erp_url)
    raised = "no"
    body: dict = {}
    try:
        async with Client(srv) as c:
            body, _ = await _call(c, "get_order_status", {"order_id": QUERY_ORDER})
    except Exception as exc:                    # noqa: BLE001
        # 走到这里就说明降级设计失败了：异常穿透了 MCP 边界。
        raised = "yes"
        log(f"[degrade] 异常穿透工具边界: {type(exc).__name__}: {exc}")
    print(f"error={body.get('error')} "
          f"retryable={str(bool(body.get('retryable'))).lower()} raised={raised}")
    return 0 if (raised == "no" and body.get("error") == "upstream_timeout") else 1


# ── breaker：连续失败后必须真的不再打 ERP ────────────────────────
async def mode_breaker(erp_url: str) -> int:
    erp, srv = _make(erp_url, threshold=3)
    tripped = False
    async with Client(srv) as c:
        # 一直打到熔断器打开为止（设了上限，免得 ERP 恢复正常时死循环）
        for _ in range(12):
            await _call(c, "get_order_status", {"order_id": QUERY_ORDER})
            if erp.breaker.state == CircuitBreaker.OPEN:
                tripped = True
                break

        # 熔断那一刻 ERP 的累计调用数。_stats 端点自身不计数，读它不会污染基准。
        total_at_trip = int(erp.stats().get("total", 0))

        # 熔断后再打 5 次。这 5 次必须既快又完全不碰 ERP——
        # verify.sh 会自己向 ERP 取数核对累计值有没有涨，不采信这里的自报数字。
        post, worst_ms = 0, 0
        for _ in range(5):
            t0 = time.monotonic()
            body, _err = await _call(c, "get_order_status", {"order_id": QUERY_ORDER})
            worst_ms = max(worst_ms, int((time.monotonic() - t0) * 1000))
            post += 1
            if body.get("error") != "circuit_open":
                log(f"[breaker] 熔断后仍走了下游路径: {body.get('error')}")

    print(f"tripped={'yes' if tripped else 'no'} erp_total_at_trip={total_at_trip} "
          f"post_trip_calls={post} fast_fail_ms={worst_ms}")
    return 0 if tripped else 1


MODES = {"dump": mode_dump, "invoke": mode_invoke, "retry": mode_retry,
         "degrade": mode_degrade, "breaker": mode_breaker}


def main() -> int:
    ap = argparse.ArgumentParser(description="Lab-03 MCP 桥接层验收探针")
    ap.add_argument("--mode", required=True, choices=sorted(MODES))
    ap.add_argument("--erp", default="https://127.0.0.1:19543")
    a = ap.parse_args()
    try:
        return asyncio.run(MODES[a.mode](a.erp))
    except Exception as exc:                    # noqa: BLE001
        # 探针自己崩掉会让验收结果不可判读（verify.sh 只会看到「无输出」），
        # 所以顶层也兜一层，把原因写进 stderr 供 results/*.err 定位。
        log(f"[{a.mode}] 探针异常: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
