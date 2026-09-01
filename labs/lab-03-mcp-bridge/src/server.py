#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""MCP Server：把遗留 ERP 的三个接口暴露成三个工具。

边界在哪里，这个文件说了算：

  - 往下：`bridge.ErpClient` 处理证书、重试、熔断。本文件不碰 TLS，也不碰退避。
  - 往上：工具**只返回结构化 dict，永不抛异常**。一个未捕获的异常会顺着 MCP
    协议冒到 host，轻则中断会话，重则把证书路径打进模型的上下文。

三个工具单一职责，绝不合并。把「查询 + 审批」揉成一个 `handle_order` 工具，
模型就再也没办法只做前一半了 —— 而前一半恰恰是遇到模糊指令时唯一安全的动作。

工具描述（docstring）是本 Lab 真正的交付物。模型没读过这里的代码，
它判断「该不该批这单」的全部依据，就是下面那几段字。
"""
from __future__ import annotations

import functools
import inspect
import re
from typing import Any

from mcp.server.mcpserver import MCPServer

from .bridge import BridgeFailure, CircuitBreaker, ErpClient, Failure

# 每个工具一份超时预算：查询要快（用户在等），写入次之，审批允许慢一点
# （它是低频、高价值操作，多等两秒远比失败重来划算）。
TIMEOUT_QUERY = 2.0
TIMEOUT_NOTE = 3.0
TIMEOUT_APPROVE = 5.0

_ORDER_ID_RE = re.compile(r"^ORD-\d{8}-\d{3}$")


def _bad_order_id(order_id: str) -> dict[str, Any]:
    return Failure(
        "invalid_order_id",
        f"订单号 {order_id!r} 不符合 ERP 的格式要求（形如 ORD-20260317-001）。"
        "请与用户核对后重新提供，重试同一个值不会有不同结果。",
        retryable=False,
    ).as_dict()


def _normalize(order_id: str) -> str | None:
    oid = (order_id or "").strip().upper()
    return oid if _ORDER_ID_RE.match(oid) else None


def _guard(fn):
    """工具层的兜底：任何异常都翻成结构化返回，绝不让它穿过 MCP 边界。

    `functools.wraps` 不只是为了好看——MCP 靠 `inspect.signature` 反推 input_schema，
    它会跟着 `__wrapped__` 找回原函数。少了这一步，三个工具的入参 schema 会退化成
    `{args, kwargs}`，模型就再也传不对 order_id 了。
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BridgeFailure as exc:
            return exc.failure.as_dict()
        except Exception as exc:                      # noqa: BLE001 - 这里就是要兜住一切
            return Failure(
                "bridge_internal_error",
                f"桥接层内部错误（{type(exc).__name__}），已被拦截未影响会话。"
                "请联系桥接层维护者；直接重试大概率仍会失败。",
                retryable=False,
            ).as_dict()
    # docstring 会原样成为工具描述送进模型上下文，缩进必须先剥掉。
    wrapper.__doc__ = inspect.cleandoc(fn.__doc__ or "")
    return wrapper


def build_server(erp_url: str, client: ErpClient | None = None) -> MCPServer:
    """构造 MCP Server。`client` 可注入，方便探针复用同一个熔断器状态。"""
    erp = client or ErpClient(erp_url, timeout=TIMEOUT_QUERY,
                              breaker=CircuitBreaker(threshold=3,
                                                     recovery_seconds=30.0))
    srv = MCPServer(
        name="erp-bridge",
        instructions=(
            "本 Server 桥接客户的遗留 ERP。所有工具都已在服务端完成身份鉴权，"
            "你不需要、也无法提供任何凭据。approve_order 是不可逆操作，"
            "仅在用户明确授权时调用。"
        ),
    )

    @srv.tool()
    @_guard
    def get_order_status(order_id: str) -> dict[str, Any]:
        """查询单个 ERP 订单的当前状态、金额、物流单号与预计送达时间。只读，不修改任何数据。

        适用场景：用户问「我的单子到哪一步了」「发货了没有」「物流单号是多少」
        「大概什么时候能到」，或者你需要先弄清订单状态才能决定下一步做什么。
        当用户的意图含糊不清（例如「帮我把这个单处理一下」）时，本工具是唯一安全的第一步——
        先查清状态并把情况讲给用户听，再请他明确接下来要做什么。

        不适用：本工具只读。写备注请改用 add_order_note；提交审批请改用 approve_order
        （且必须先拿到用户的明确授权）。不要用本工具去「顺手把事办了」。

        参数：order_id —— ERP 订单号，格式形如 ORD-20260317-001
        （ORD- 前缀 + 8 位日期 + 3 位序号），大小写不敏感，前后空格会被忽略。

        返回：成功时 ok=true，含 order_id / status / amount_cents / tracking_no /
        eta / note_count；失败时 ok=false，含 error、message、retryable 三个字段。
        retryable=true（例如 upstream_timeout、upstream_unavailable）表示下游临时抽风，
        稍后重试有意义；retryable=false（例如 order_not_found）表示重试一万次也不会变，
        应当直接把原因告诉用户并请他核对单号。
        """
        oid = _normalize(order_id)
        if oid is None:
            return _bad_order_id(order_id)
        row = erp.get_order(oid, timeout=TIMEOUT_QUERY)
        return {
            "ok": True,
            "order_id": row.get("ORDER_ID"),
            "status": row.get("STATUS"),
            "amount_cents": row.get("AMOUNT_CENTS"),
            "tracking_no": row.get("TRACKING_NO"),
            "eta": row.get("ETA"),
            "note_count": len(row.get("NOTES") or []),
        }

    @srv.tool()
    @_guard
    def add_order_note(order_id: str, text: str) -> dict[str, Any]:
        """在指定 ERP 订单上追加一条文字备注。写入操作，但可安全重复——
        重复写入最多多出一条记录，代价可控。

        适用场景：用户明确要求「记一笔」「留个记录」「备注一下」，
        或者需要把与客户的沟通结论落到订单上，例如「已电话确认周末送货」。
        用户转述客户的催促、抱怨、诉求时，把它记成备注通常是恰当且安全的动作。

        不适用：备注只是留痕，它不会改变订单状态，更不等于审批。
        如果用户话里出现了「审批」二字却没有明确授权你去批，写备注是安全的，
        调用 approve_order 不是。只想知道订单进展请改用 get_order_status。

        参数：order_id —— 订单号，格式形如 ORD-20260317-001；
        text —— 备注正文，不能为空，写成完整的一句话。
        用户往往不会逐字口述备注内容（例如只说「我刚跟客户电话确认过了，留个记录」），
        这时请直接把他的意思概括成一句话填进 text，不必反问他要写什么——
        备注是可重复、可追加的低风险操作，写错了再补一条即可。

        返回：成功时 ok=true，含 order_id 与 note_count（写入后的备注总数）；
        失败时 ok=false，含 error、message、retryable。retryable=true 说明是 ERP 侧
        临时故障，可以稍后重试；retryable=false（例如 order_not_found、
        note_text_required）说明是入参或业务问题，重试无用，应先与用户确认。
        """
        oid = _normalize(order_id)
        if oid is None:
            return _bad_order_id(order_id)
        body = (text or "").strip()
        if not body:
            return Failure("note_text_required", "备注正文为空，请补全后再调用。",
                           retryable=False).as_dict()
        res = erp.add_note(oid, body, timeout=TIMEOUT_NOTE)
        return {"ok": True, "order_id": res.get("ORDER_ID"),
                "note_count": res.get("NOTE_COUNT")}

    @srv.tool()
    @_guard
    def approve_order(order_id: str) -> dict[str, Any]:
        """提交订单审批，把订单状态从待审批推进到已审批。

        【这是不可逆操作】审批一旦提交，本工具没有任何撤销手段，钱就批出去了。
        误触发一次就是一起事故，不存在「重试一下就好」这种说法。

        适用场景：仅在用户**明确表达审批授权**时调用。判断标准是：说话人自己是决策人，
        且句子的动词直接指向「批准」这个动作。例如「ORD-20260317-002 审批通过，你直接批了吧」
        「我同意，走审批」「批准这一单」。

        不适用（这段比上一段重要）：模糊表述不构成授权。以下情形一律不要调用本工具——
        - 「帮我把 ORD-20260317-002 处理一下」：「处理」语义模糊，不是审批授权；
        - 「这单怎么还没动静／是不是卡住了」：这是在问进度，请改用 get_order_status；
        - 「客户说 ORD-20260317-002 的审批都走了三天了」：这是转述他人抱怨，
          句中的「审批」是名词不是授权，请改用 get_order_status 或 add_order_note；
        - 用户只是提到了「审批」这个词，却没有说他同意、批准或让你去批。
        遇到上述情形，正确做法是先查状态或记备注，再请用户明确确认是否要审批。
        宁可多问一句，不可擅自批准。

        参数：order_id —— 待审批订单号，格式形如 ORD-20260317-002。

        返回：成功时 ok=true，含 order_id 与 status=APPROVED；
        失败时 ok=false，含 error、message、retryable。
        特别注意 order_not_in_pending_approval（订单当前不处于待审批状态）
        与 order_not_found 两种错误的 retryable 均为 false——不要重试，
        请把原因原样告诉用户。只有 retryable=true 的错误（如 upstream_timeout）
        才值得稍后再试，且重试前应再次向用户确认授权仍然有效。
        """
        oid = _normalize(order_id)
        if oid is None:
            return _bad_order_id(order_id)
        res = erp.approve(oid, timeout=TIMEOUT_APPROVE)
        return {"ok": True, "order_id": res.get("ORDER_ID"),
                "status": res.get("STATUS")}

    srv._erp_client = erp          # 探针用；不属于 MCP 协议表面
    return srv
