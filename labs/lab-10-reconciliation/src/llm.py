#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""可选的模型增强：只做诊断报告的可读性复述与复核提示，不做判定。

分工是这个 Lab 的一个立场：**根因由规则定，模型只负责把结论讲清楚。**
三类根因都有确定性判据（见 `diagnose.py`），用规则判更稳、更快、更便宜；
让模型去判，等于把一个可判定问题换成一个概率问题。

所以这里的调用有两条硬约束：
1. 模型的输出**不进入 quarantine.root_cause**，只进 report.json 的说明字段；
2. 模型给出的根因若与规则不一致，记进报告的 `model_disagreement` 供人工留意，
   但仍以规则为准——模型不是裁判。

Key 只从环境变量读，绝不写进任何文件、也不打进日志。
用标准库 urllib 发请求，不为一次 HTTP POST 引入 SDK 依赖。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE = "https://api.deepseek.com"
MODEL = "deepseek-chat"


def has_key() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def chat(prompt: str, *, system: str | None = None,
         timeout: float = 30.0, max_tokens: int = 400) -> str:
    """发一次单轮对话，返回纯文本。失败直接抛，由调用方决定怎么降级。"""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("没有 DEEPSEEK_API_KEY")
    base = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE).rstrip("/")
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    body = json.dumps({"model": MODEL, "messages": messages,
                       "temperature": 0.0, "max_tokens": max_tokens},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return (payload["choices"][0]["message"]["content"] or "").strip()


SYSTEM = ("你是财务对账系统的值班工程师。收到的是一条已经由确定性规则定过根因的"
          "不一致记录，你的任务不是重新判定，而是把它写成人能在两分钟内复核完的说明。"
          "只输出 JSON，不要代码块围栏。")

PROMPT = """\
以下是一条对账不一致记录的全部证据。

事务号：{txn_id}
系统 A（订单系统，金额单位分，时间带 +08:00）：{a}
系统 B（财务台账，金额单位分，时间无偏移、约定为北京时间）：{b}
该事务的事件流（seq 是到达顺序，occurred_at 是业务发生时间）：
{events}

规则判定的根因：{root_cause}
规则给出的依据：{detail}
已起草的补偿 SQL（尚未执行，等待人工复核）：
{sql}

请输出 JSON，字段如下：
- "root_cause"：你独立判断的根因，只能是 timezone / out_of_order / model_mismatch / unknown 之一
- "explanation"：给复核人看的说明，2-3 句，讲清楚发生了什么以及影响了什么账
- "review_note"：复核这份补偿 SQL 时最该确认的一点，1 句
"""


def enrich(txn_id: str, a: dict, b: dict, events: list[dict],
           root_cause: str, detail: str, sql: list[str],
           timeout: float = 30.0) -> dict:
    """让模型复述一条诊断。任何失败都降级成规则文本，不影响主流程。"""
    trace = "\n".join(
        f"  seq={e['seq']} {e['kind']} status={e['status']} "
        f"amount_cents={e['amount_cents']} occurred_at={e['occurred_at']} src={e['source']}"
        for e in sorted(events, key=lambda x: x["seq"])) or "  （无事件）"
    prompt = PROMPT.format(
        txn_id=txn_id, a=json.dumps(a, ensure_ascii=False),
        b=json.dumps(b, ensure_ascii=False), events=trace,
        root_cause=root_cause, detail=detail, sql="\n".join(sql))
    try:
        raw = chat(prompt, system=SYSTEM, timeout=timeout)
        text = raw.strip()
        if text.startswith("```"):  # 模型偶尔还是会套围栏
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0]
        data = json.loads(text[text.index("{"):text.rindex("}") + 1])
        return {
            "explanation": str(data.get("explanation", "")).strip(),
            "review_note": str(data.get("review_note", "")).strip(),
            "model_root_cause": str(data.get("root_cause", "")).strip(),
            "model_disagreement": str(data.get("root_cause", "")).strip() != root_cause,
        }
    except Exception as exc:  # noqa: BLE001 — 模型是增强项，坏了不能拖垮对账
        return {"model_error": f"{type(exc).__name__}: {str(exc)[:160]}"}
