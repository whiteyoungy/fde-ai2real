# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""评估运行器：跑三层评估集，输出结构化 JSON 结果 + 人类可读摘要。

用法：
    python3 -m src.run_eval --config configs/system_baseline.yaml --output results/x.json --summary
    python3 -m src.run_eval --config configs/system_degraded.yaml --output results/y.json --judge llm
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from src import dataset_loader, sut
from src.llm_client import default_client, get_client_config
from src.scorers import (
    EvalResult,
    _pass_rate,
    make_behavior_checker,
    make_deterministic_faithfulness_judge,
    make_llm_faithfulness_judge,
    score_adversarial_case,
    score_golden_case,
    score_regression_case,
)


def _recall_at_k(case_extra_by_id: dict, retrieved_by_id: dict) -> float | None:
    scored = []
    for case_id, extra in case_extra_by_id.items():
        reference_ids = extra.get("reference_context_ids")
        if not reference_ids:
            continue
        retrieved = set(retrieved_by_id.get(case_id, []))
        reference = set(reference_ids)
        scored.append(len(retrieved & reference) / len(reference))
    if not scored:
        return None
    return sum(scored) / len(scored)


def run(config_path: str, judge_mode: str = "proxy") -> dict:
    config = sut.load_system_config(config_path)
    kb = dataset_loader.load_kb()
    cases_by_layer = dataset_loader.load_all_cases()

    if judge_mode == "llm":
        client = default_client()
        golden_judge_default = make_llm_faithfulness_judge(client.chat)
    else:
        golden_judge_default = None  # 每条用例单独用它自己的 key_facts 构造 judge_fn

    results: list[EvalResult] = []
    retrieved_by_id: dict[str, list[str]] = {}
    golden_extra_by_id: dict[str, dict] = {}
    regression_extra_by_id: dict[str, dict] = {}

    for case in cases_by_layer["golden"]:
        output, retrieved = sut.answer_case(case, kb, config)
        retrieved_by_id[case.id] = retrieved
        golden_extra_by_id[case.id] = case.extra
        if judge_mode == "llm":
            judge_fn = golden_judge_default
        else:
            judge_fn = make_deterministic_faithfulness_judge(case.extra.get("key_facts") or [])
        context_texts = [kb[i]["content"] for i in retrieved if i in kb]
        results.append(score_golden_case(case, output, context_texts, judge_fn))

    for case in cases_by_layer["regression"]:
        output, retrieved = sut.answer_case(case, kb, config)
        retrieved_by_id[case.id] = retrieved
        regression_extra_by_id[case.id] = case.extra
        results.append(score_regression_case(case, output))

    for case in cases_by_layer["adversarial"]:
        output, _retrieved = sut.answer_case(case, kb, config)
        checker = make_behavior_checker(case)
        results.append(score_adversarial_case(case, output, checker))

    by_layer = {"golden": [], "adversarial": [], "regression": []}
    for r in results:
        by_layer[r.layer].append(r)

    combined_extra = {**golden_extra_by_id, **regression_extra_by_id}
    recall_at_k = _recall_at_k(combined_extra, retrieved_by_id)
    golden_scores = [r.score for r in by_layer["golden"]]
    avg_faithfulness = sum(golden_scores) / len(golden_scores) if golden_scores else None

    aggregate = {
        "golden_pass_rate": _pass_rate(by_layer["golden"]),
        "adversarial_pass_rate": _pass_rate(by_layer["adversarial"]),
        "regression_pass_rate": _pass_rate(by_layer["regression"]),
        "recall_at_k": recall_at_k,
        "avg_faithfulness": avg_faithfulness,
    }

    client_cfg = get_client_config()
    payload = {
        "meta": {
            "config": str(config_path),
            "variant": config.variant,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "judge_mode": judge_mode,
            "judge_model": client_cfg.model if judge_mode == "llm" else None,
            "layer_counts": {k: len(v) for k, v in cases_by_layer.items()},
        },
        "aggregate": aggregate,
        "results": [
            {
                "case_id": r.case_id,
                "layer": r.layer,
                "score": r.score,
                "passed": r.passed,
                "detail": r.detail,
                "severity": r.severity,
            }
            for r in results
        ],
    }
    return payload


def print_summary(payload: dict) -> str:
    agg = payload["aggregate"]
    lines = [
        f"== 评估摘要（配置: {payload['meta']['variant']}） ==",
        f"黄金集通过率:   {agg['golden_pass_rate']:.1%}",
        f"对抗集通过率:   {agg['adversarial_pass_rate']:.1%}",
        f"回归集通过率:   {agg['regression_pass_rate']:.1%}",
    ]
    if agg["recall_at_k"] is not None:
        lines.append(f"检索 Recall@k: {agg['recall_at_k']:.1%}")
    if agg["avg_faithfulness"] is not None:
        lines.append(f"黄金集平均 faithfulness: {agg['avg_faithfulness']:.3f}")
    last_line = (
        f"基线通过率: golden={agg['golden_pass_rate']:.1%} "
        f"adversarial={agg['adversarial_pass_rate']:.1%} "
        f"regression={agg['regression_pass_rate']:.1%} "
        f"recall@k={agg['recall_at_k']:.1%}" if agg["recall_at_k"] is not None else
        f"基线通过率: golden={agg['golden_pass_rate']:.1%}"
    )
    lines.append(last_line)
    text = "\n".join(lines)
    print(text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Lab-05 评估运行器")
    parser.add_argument("--config", required=True, help="系统配置 yaml 路径")
    parser.add_argument("--output", required=True, help="结果 JSON 输出路径")
    parser.add_argument("--judge", choices=["proxy", "llm"], default="proxy",
                         help="黄金集 judge_fn：proxy=确定性代理（默认，门禁用）；llm=真实调用双路径 LLM")
    parser.add_argument("--summary", action="store_true", help="打印人类可读摘要")
    args = parser.parse_args()

    payload = run(args.config, judge_mode=args.judge)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.summary:
        print_summary(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
