# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""加载三层评估集与支撑知识库 JSONL 文件。"""
from __future__ import annotations

import json
from pathlib import Path

from src.scorers import EvalCase

LAB_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = LAB_ROOT / "datasets"

_CORE_FIELDS = {"id", "layer", "query", "reference_answer", "expected_behavior"}


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name} 第 {line_no} 行不是合法 JSON: {exc}") from exc
    return rows


def _row_to_case(row: dict) -> EvalCase:
    extra = {k: v for k, v in row.items() if k not in _CORE_FIELDS}
    return EvalCase(
        id=row["id"],
        layer=row["layer"],
        query=row["query"],
        reference_answer=row.get("reference_answer"),
        expected_behavior=row.get("expected_behavior"),
        extra=extra,
    )


def load_cases(layer: str) -> list[EvalCase]:
    path = DATASETS_DIR / f"{layer}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"找不到数据集文件: {path}")
    return [_row_to_case(row) for row in _read_jsonl(path)]


def load_all_cases() -> dict[str, list[EvalCase]]:
    return {
        "golden": load_cases("golden"),
        "adversarial": load_cases("adversarial"),
        "regression": load_cases("regression"),
    }


def load_kb(path: Path | None = None) -> dict[str, dict]:
    kb_path = path or (DATASETS_DIR / "kb.jsonl")
    if not kb_path.exists():
        raise FileNotFoundError(f"找不到知识库文件: {kb_path}")
    kb = {}
    for row in _read_jsonl(kb_path):
        kb[row["id"]] = {"keywords": row.get("keywords", []), "content": row["content"]}
    return kb
