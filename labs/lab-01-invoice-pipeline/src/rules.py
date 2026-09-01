# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""确定性规则层：先用规则做管道能确定的判断，剩下的才交给模型。

本 Lab 里确定性规则承担两件事：
1. **准入门槛**：抽不到文本（截断文件/扫描件）直接隔离，根本不调用模型——
   不该让模型对着空字符串去"编"一份发票出来。
2. **抽取草稿**：用标签+正则从原文里抠一版候选字段，作为 prompt 里的提示，
   也作为模型多轮自纠错仍失败时的兜底候选（草稿本身仍必须过强类型校验 +
   grounding 才会被采用，见 run_pipeline.py 的 `rule_fallback` 分支）。

这一层刻意写得"笨"——只认这批夹具里出现过的标签词和格式，换一批发票模板
大概率要重写。这是有意的取舍：正则解析器的维护成本会随着单据模板数量线性
增长，这也是为什么真正的抽取主力仍然是模型，规则只做"模型靠得住时兜底、
模型不可用时兜底"的两端，不覆盖中间。
"""
from __future__ import annotations

import re

from .textutil import flatten

MIN_TEXT_CHARS = 10


def empty_text_reason(norm_text: str) -> str | None:
    """文本抽取产出是否过短到该直接隔离、不调用模型。"""
    n = len(norm_text.strip())
    if n < MIN_TEXT_CHARS:
        return f"文本抽取为空或过短（{n} 字符），判定为扫描件/截断文件，未调用模型"
    return None


_INVOICE_NO_LABELS = (r"发票号码", r"单据编号", r"Invoice\s*No\.?")
_DATE_LABEL = re.compile(
    r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})\s*日?"
)
_EXCL_LABELS = ("金额（不含税）", "合计金额", "Net Amount", "金额")
_TAX_LABELS = ("税额", "Tax")
_TOTAL_LABELS = ("价税合计", "Gross Total", "合计")


def _find_amount(text: str, label: str) -> float | None:
    pattern = re.escape(label) + r".{0,20}?([+-]?[\d,]+\.\d+)"
    if label == "合计":
        # 避免命中"合计金额"（那是不含税金额的标签，不是价税合计）。
        pattern = r"合计(?!金额)" + r".{0,20}?([+-]?[\d,]+\.\d+)"
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _find_first_amount(text: str, labels: tuple[str, ...]) -> float | None:
    for label in labels:
        v = _find_amount(text, label)
        if v is not None:
            return v
    return None


def parse_draft(norm_text: str) -> dict:
    """从归一化后的原文里抠一版候选字段草稿；抠不到的字段直接不出现在结果里。"""
    flat = flatten(norm_text)
    draft: dict = {}

    m = re.search(r"INV-\d{4}-\d{6}", flat)
    if m:
        draft["invoice_no"] = m.group(0)

    dm = _DATE_LABEL.search(flat)
    if dm:
        y, mo, d = (int(x) for x in dm.groups())
        if 2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31:
            draft["invoice_date"] = f"{y:04d}-{mo:02d}-{d:02d}"

    excl = _find_first_amount(norm_text, _EXCL_LABELS)
    tax = _find_first_amount(norm_text, _TAX_LABELS)
    total = _find_first_amount(norm_text, _TOTAL_LABELS)

    if excl is None and total is not None and (tax is None or tax == 0):
        # 常见形态：单据只有"合计"、没有单独的"不含税金额"栏，说明本就不含税。
        excl = total
        if tax is None:
            tax = 0.0

    if excl is not None:
        draft["amount_excl_tax"] = excl
    if tax is not None:
        draft["tax_amount"] = tax
    if total is not None:
        draft["total"] = total

    return draft
