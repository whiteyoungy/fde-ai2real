# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""文本归一化工具。

脏 PDF 摄取管道里，字符编码层面的"脏"往往比字段内容层面的脏更隐蔽：
- 全角数字/标点（NFKC 才能归一）；
- CJK 字体渲染 ASCII 连字符时，pdftotext 抽出来的往往不是 U+002D，而是
  U+2011（NON-BREAKING HYPHEN）之类的近似连字符——这是本 Lab 用
  NotoSerifCJK 字体画所有文本时的真实副作用，不是人为制造的脏，但一样会
  让 "INV-2026-000101" 和正则/字符串比较对不上，必须显式收敛。
"""
from __future__ import annotations

import re
import unicodedata

# 各种"看起来像连字符/减号"但不是 U+002D 的字符，统一收敛为 ASCII '-'。
# 包含：HYPHEN、NON-BREAKING HYPHEN、FIGURE DASH、EN DASH、EM DASH、MINUS SIGN。
_DASH_LIKE = "‐‑‒–—−"
_DASH_TABLE = {ord(ch): "-" for ch in _DASH_LIKE}


def normalize(raw: str) -> str:
    """NFKC 归一化 + 连字符收敛。管道里所有下游处理都应该先过这一步。"""
    if not raw:
        return ""
    s = unicodedata.normalize("NFKC", raw)
    s = s.translate(_DASH_TABLE)
    return s


def flatten(s: str) -> str:
    """去掉所有空白，用于处理跨行断开的字段（如发票号被换行截断）。"""
    return re.sub(r"\s+", "", s)


def flatten_for_grounding(s: str) -> str:
    """去空白 + 去千分位逗号，用于"数值是否真的出现在原文里"的子串检索。"""
    return re.sub(r"[\s,，]", "", s)
