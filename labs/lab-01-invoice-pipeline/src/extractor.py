# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""模型抽取 + 强类型校验 + 自纠错回灌循环（第 11 章 11.1 节的核心机制）。

流程：
    模型抽取 → parse_json_loose → Pydantic 强制校验 + grounding 校验
        → 通过：放行
        → 失败：把错误信息（不是原始异常堆栈本身，而是提炼过的人类可读描述，
                 附带失败的原始输出）**回灌进下一轮的 prompt**，强制模型自纠正
        → 若干轮仍失败：交回给调用方决定隔离（run_pipeline.py 里还有一层
          确定性规则兜底，见该文件的 `rule_fallback` 分支）。

可替换项：换别的 LLM SDK / 换 Prompt 策略只需要改这个文件；
`InvoiceExtraction` 的字段集合是这里与 schema.py 之间的契约。
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

from pydantic import ValidationError

from .llm_client import LLMClient
from .schema import GroundingError, InvoiceExtraction, check_grounding

SYSTEM_PROMPT = (
    "你是发票字段抽取助手。只输出一个 JSON 对象，不要输出任何解释、不要用 "
    "Markdown 代码块。JSON 必须包含且只包含这 5 个字段：\n"
    "invoice_no（字符串，形如 INV-2026-000101）、\n"
    "invoice_date（字符串，YYYY-MM-DD）、\n"
    "amount_excl_tax（数字，不含税金额）、\n"
    "tax_amount（数字，税额）、\n"
    "total（数字，价税合计/总金额）。\n"
    "所有数值必须直接来自原文，禁止编造或猜测。如果原文明确写着这是红字/负数发票，"
    "对应金额也必须是负数。如果原文只有一个不区分税的'合计'金额、没有单独税额栏，"
    "令 tax_amount=0 且 amount_excl_tax 等于该合计金额。如果原文里根本找不到发票号码"
    "或金额，就照抄原文的缺失情况，不要为了凑出合规格式而编一个数字或编号出来——"
    "宁可让对应字段留空字符串或 0，也不要编造。"
)


def build_user_prompt(
    norm_text: str,
    draft: dict,
    prior_error: Optional[str] = None,
    prior_raw: Optional[str] = None,
) -> str:
    parts = [f"发票原文（已做归一化处理）：\n---\n{norm_text.strip()}\n---"]
    if draft:
        parts.append(
            "一个候选草稿（正则粗抽，可能有错或不全，仅供参考，请以原文为准核对）：\n"
            + json.dumps(draft, ensure_ascii=False)
        )
    if prior_error:
        parts.append(
            "上一轮你的输出没有通过校验，错误信息如下，请仔细核对原文后修正，"
            "只输出修正后的完整 JSON：\n"
            f"上一轮输出：{prior_raw!r}\n"
            f"校验错误：{prior_error}"
        )
    parts.append("现在请输出 JSON：")
    return "\n\n".join(parts)


def parse_json_loose(raw: str) -> dict:
    """从模型输出里尽量宽容地摘出一个 JSON 对象（容忍代码块围栏、前后缀废话）。"""
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"未在模型输出中找到 JSON 对象：{s[:200]!r}")
    snippet = s[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败（{e}）；原始片段：{snippet[:200]!r}") from e


def extract_with_self_correction(
    client: LLMClient,
    norm_text: str,
    draft: dict,
    grounding_text: str,
    max_attempts: int,
    on_retry: Optional[Callable[[int, str], None]] = None,
) -> tuple[Optional[dict], list[dict], bool]:
    """跑一轮"抽取 → 校验 → 失败则回灌重试"循环。

    返回 (fields, attempts, success)：
    - fields：校验通过后的字段字典（含由 Pydantic 归一化过的值），失败为 None；
    - attempts：每一轮的记录（attempt 序号、原始输出、是否通过、错误信息），
      落盘到 results 里作为"自纠错确实发生过"的证据；
    - success：是否在 max_attempts 轮内拿到合规结果。
    """
    attempts: list[dict] = []
    prior_error: Optional[str] = None
    prior_raw: Optional[str] = None

    for attempt in range(1, max_attempts + 1):
        if attempt > 1 and on_retry:
            on_retry(attempt, prior_error or "")

        user_prompt = build_user_prompt(norm_text, draft, prior_error, prior_raw)
        try:
            raw = client.chat(user_prompt, system=SYSTEM_PROMPT, temperature=0.0, max_tokens=280)
        except Exception as e:  # 网络/超时/服务不可用——记为一次失败尝试，允许重试
            err = f"LLM 调用异常：{type(e).__name__}: {e}"
            attempts.append({"attempt": attempt, "raw_output": None, "valid": False, "error": err})
            prior_error, prior_raw = err, None
            continue

        try:
            data = parse_json_loose(raw)
            obj = InvoiceExtraction(**data)
            fields = obj.model_dump()
            check_grounding(fields, grounding_text)
        except (ValueError, ValidationError) as e:
            err = str(e)
            attempts.append({"attempt": attempt, "raw_output": raw, "valid": False, "error": err})
            prior_error, prior_raw = err, raw
            continue

        attempts.append({"attempt": attempt, "raw_output": raw, "valid": True, "error": None})
        return fields, attempts, True

    return None, attempts, False
