# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""verify.sh [1/5]：三层评估集加载与基本 schema 校验。"""
from __future__ import annotations

import sys

from src import dataset_loader

MIN_COUNTS = {"golden": 20, "adversarial": 8, "regression": 5}
REQUIRED_FIELDS = {
    "golden": ["id", "layer", "query"],
    "adversarial": ["id", "layer", "query", "expected_behavior"],
    "regression": ["id", "layer", "query", "reference_answer"],
}


def main() -> int:
    problems: list[str] = []
    counts: dict[str, int] = {}

    try:
        kb = dataset_loader.load_kb()
    except Exception as exc:  # noqa: BLE001
        print(f"加载 kb.jsonl 失败: {exc}", file=sys.stderr)
        return 1

    try:
        cases_by_layer = dataset_loader.load_all_cases()
    except Exception as exc:  # noqa: BLE001
        print(f"加载评估集失败: {exc}", file=sys.stderr)
        return 1

    for layer, cases in cases_by_layer.items():
        counts[layer] = len(cases)
        if len(cases) < MIN_COUNTS[layer]:
            problems.append(f"{layer} 集只有 {len(cases)} 条，最少要求 {MIN_COUNTS[layer]} 条")

        seen_ids = set()
        for case in cases:
            if case.id in seen_ids:
                problems.append(f"{layer} 集里 id 重复: {case.id}")
            seen_ids.add(case.id)

            if case.layer != layer:
                problems.append(f"{case.id} 的 layer 字段是 {case.layer!r}，应为 {layer!r}")

            for field_name in REQUIRED_FIELDS[layer]:
                value = getattr(case, field_name, None) or case.extra.get(field_name)
                if not value:
                    problems.append(f"{case.id} 缺少必填字段 {field_name}")

            ref_ids = case.extra.get("reference_context_ids") or []
            for kb_id in ref_ids:
                if kb_id not in kb:
                    problems.append(f"{case.id} 引用了不存在的知识库条目 {kb_id}")

    if problems:
        print("三层评估集校验失败：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"golden={counts['golden']} adversarial={counts['adversarial']} regression={counts['regression']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
