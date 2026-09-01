# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""发票抽取结果的强类型校验层（第 11 章 11.1 节：模型抽取 → 强制校验 → 自纠错）。

可替换项：换校验框架（比如从 Pydantic 换成 `jsonschema` 或手写 dataclass + 校验
函数）只需要改这一个文件，只要保持三样东西不变：
1. `InvoiceExtraction`（或替代品）校验失败时抛出的异常里带着人类可读、可
   直接回灌给模型的错误信息；
2. `check_grounding()` 的签名与语义（字段值必须能在原文里找到，防止模型编造）；
3. `run_pipeline.py` / `extractor.py` 依赖的字段名集合
   （invoice_no / invoice_date / amount_excl_tax / tax_amount / total）。
"""
from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ValidationError, field_validator, model_validator

__all__ = ["InvoiceExtraction", "ValidationError", "GroundingError", "check_grounding"]

_INVOICE_NO_RE = re.compile(r"INV-\d{4}-\d{6}")


class GroundingError(ValueError):
    """字段通过了 Pydantic 的类型/格式校验，但值在原文里找不到依据（疑似模型编造）。"""


class InvoiceExtraction(BaseModel):
    invoice_no: str
    invoice_date: str
    amount_excl_tax: float
    tax_amount: float
    total: float

    # ---- 金额字段：允许模型返回带千分位逗号的字符串，清洗后再交给 float 校验 ----
    @field_validator("amount_excl_tax", "tax_amount", "total", mode="before")
    @classmethod
    def _clean_amount(cls, v):
        if isinstance(v, str):
            cleaned = v.replace(",", "").replace("，", "").strip()
            if cleaned in ("", "None", "null", "N/A", "-"):
                raise ValueError(f"金额字段为空或不是数字：{v!r}")
            return cleaned
        return v

    # ---- 发票号：不允许为空，必须匹配 INV-YYYY-NNNNNN；允许模型误插空格 ----
    @field_validator("invoice_no")
    @classmethod
    def _check_invoice_no(cls, v: str) -> str:
        v = (v or "").replace(" ", "").strip()
        if not v:
            raise ValueError("invoice_no 为空：原文中没有可确认的发票号码，禁止编造")
        if not _INVOICE_NO_RE.fullmatch(v):
            raise ValueError(
                f"invoice_no 格式非法，需匹配 INV-YYYY-NNNNNN（六位流水号）：{v!r}"
            )
        return v

    # ---- 日期：接受 ISO(YYYY-MM-DD) 或 YYYY/MM/DD，统一收敛为 ISO 输出 ----
    @field_validator("invoice_date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("invoice_date 为空：原文中没有完整日期，禁止编造")
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            pass
        m = re.fullmatch(r"(\d{4})[/.](\d{1,2})[/.](\d{1,2})", v)
        if m:
            y, mo, d = (int(x) for x in m.groups())
            try:
                return date(y, mo, d).isoformat()
            except ValueError as e:
                raise ValueError(f"invoice_date 数值不构成合法日期：{v!r}（{e}）") from e
        raise ValueError(f"invoice_date 无法解析为合法日期（需 YYYY-MM-DD）：{v!r}")

    # ---- 跨字段一致性：不含税金额 + 税额 = 价税合计（红字发票允许全部为负）----
    @model_validator(mode="after")
    def _check_arith(self) -> "InvoiceExtraction":
        lhs = self.amount_excl_tax + self.tax_amount
        tol = max(0.02, abs(self.total) * 0.001)
        if abs(lhs - self.total) > tol:
            raise ValueError(
                f"金额不自洽：amount_excl_tax({self.amount_excl_tax}) + "
                f"tax_amount({self.tax_amount}) = {lhs} != total({self.total})，"
                f"容差 ±{tol:.2f}"
            )
        return self


def check_grounding(fields: dict, grounding_text: str) -> None:
    """校验关键字段的值确实"扎根"在原文里，而不是模型凭 schema 编出来的合规值。

    这是本 Lab 防"模型编造发票号/金额"的核心防线（对应 bad-10 夹具）：光靠
    Pydantic 的格式校验挡不住模型编一个格式正确但原文里根本不存在的编号。

    `grounding_text` 必须是已经去空白、去千分位逗号的归一化原文
    （见 `textutil.flatten_for_grounding`），调用方负责准备好。
    """
    errors = []

    inv_no = (fields.get("invoice_no") or "").replace(" ", "")
    if inv_no and inv_no not in grounding_text:
        errors.append(f"invoice_no {fields.get('invoice_no')!r} 未在原文中找到，疑似模型编造")

    for key in ("amount_excl_tax", "tax_amount", "total"):
        val = fields.get(key)
        if val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if fval == 0:
            # 0 是常见的"该字段本就不存在"的合法默认值（如无税额栏），不强制要求原文出现字面 0。
            continue
        absval = abs(fval)
        candidates = [f"{absval:.2f}"]
        if absval == int(absval):
            candidates.append(f"{int(absval)}")
        if not any(c in grounding_text for c in candidates):
            errors.append(f"{key}={val} 未在原文中找到对应数字，疑似模型编造")

    if errors:
        raise GroundingError("；".join(errors))
