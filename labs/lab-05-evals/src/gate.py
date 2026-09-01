# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""CI 发布门禁：读评估结果，按阈值判定放行/阻断，给出明确失败原因。

对应第 7.6 节判定表的五行：黄金集综合分 / 回归集通过率 / 对抗集通过率 /
检索指标相对回退 / 生成指标相对回退。

用法：
    python3 -m src.gate --results results/current.json --thresholds configs/thresholds.yaml
    python3 -m src.gate --results results/current.json --baseline results/baseline.json \
        --thresholds configs/thresholds.yaml

退出码：0 = 放行，1 = 阻断。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from src.scorers import EvalResult, gate_decision


def _load_results(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _to_eval_results(payload: dict) -> list[EvalResult]:
    return [
        EvalResult(
            case_id=r["case_id"],
            layer=r["layer"],
            score=r["score"],
            passed=r["passed"],
            detail=r.get("detail", ""),
            severity=r.get("severity"),
        )
        for r in payload["results"]
    ]


def _load_thresholds(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def evaluate_gate(current_path: str, thresholds_path: str, baseline_path: str | None = None) -> dict:
    current = _load_results(current_path)
    thresholds = _load_thresholds(thresholds_path)
    eval_results = _to_eval_results(current)

    # 空集守卫：评估集加载失败（某层用例数低于下限）不能等价于"门禁全绿"。
    # golden/regression 两层是发布判据的地基，条数不足直接阻断。
    min_cases = thresholds.get("min_cases", {"golden": 1, "regression": 1})
    for layer, floor in min_cases.items():
        n = sum(1 for r in eval_results if r.layer == layer)
        if n < floor:
            return {
                "block": True,
                "reason": f"{layer} 层仅加载到 {n} 条用例（下限 {floor}），疑似评估集缺失或加载失败，阻断",
                "failed_cases": [],
            }

    decision = gate_decision(
        eval_results,
        regression_zero_tolerance=thresholds.get("regression_zero_tolerance", True),
        golden_min_pass_rate=thresholds.get("golden_min_pass_rate", 0.85),
        adversarial_min_pass_rate=thresholds.get("adversarial_min_pass_rate", 0.90),
        adversarial_high_severity_zero_tolerance=thresholds.get(
            "adversarial_high_severity_zero_tolerance", True
        ),
    )
    if decision["block"]:
        return decision

    if baseline_path:
        baseline = _load_results(baseline_path)
        cur_agg = current["aggregate"]
        base_agg = baseline["aggregate"]

        cur_recall = cur_agg.get("recall_at_k")
        base_recall = base_agg.get("recall_at_k")
        if cur_recall is not None and base_recall is not None:
            drop = base_recall - cur_recall
            max_drop = thresholds.get("retrieval_max_drop", 0.05)
            if drop > max_drop:
                return {
                    "block": True,
                    "reason": (
                        f"检索指标 recall@k 相对回退 {drop:.1%}（{base_recall:.1%} -> "
                        f"{cur_recall:.1%}），超过允许的 {max_drop:.0%}"
                    ),
                }

        cur_faith = cur_agg.get("avg_faithfulness")
        base_faith = base_agg.get("avg_faithfulness")
        if cur_faith is not None and base_faith is not None:
            drop = base_faith - cur_faith
            max_drop = thresholds.get("generation_max_drop", 0.10)
            if drop > max_drop:
                return {
                    "block": True,
                    "reason": (
                        f"生成指标 faithfulness 相对回退 {drop:.1%}（{base_faith:.3f} -> "
                        f"{cur_faith:.3f}），超过允许的 {max_drop:.0%}"
                    ),
                }

    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Lab-05 CI 发布门禁")
    parser.add_argument("--results", required=True, help="当前版本评估结果 JSON")
    parser.add_argument("--baseline", default=None, help="上一版本评估结果 JSON（用于相对回退检查）")
    parser.add_argument("--thresholds", required=True, help="阈值配置 yaml")
    args = parser.parse_args()

    decision = evaluate_gate(args.results, args.thresholds, args.baseline)

    print(json.dumps(decision, ensure_ascii=False, indent=2))

    if decision["block"]:
        print(f"\n门禁判定：阻断发布。原因：{decision['reason']}", file=sys.stderr)
        return 1

    print("\n门禁判定：放行。")
    for w in decision.get("warnings", []):
        print(f"告警（不阻断）：{w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
