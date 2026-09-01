#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""成本归因与看板。

    python3 -m src.cost --ingest URL --pricing fixtures/pricing.json --out results
    → 打印每次调用的成本与按业务动作聚合的看板
    → 末行 actions=N calls=N total_cny=..
    → 写出 results/cost_report.json

—— 为什么算到业务动作上 ——
「这个月花了 800 块」对业务方没有意义，因为它没有分母。
「每处理一张工单花 0.06 元」才有意义——它能直接和人工成本比。
所以看板的主键是业务动作（answer_question / summarize_ticket / draft_reply），
不是模型名，也不是 token 数。一次业务动作可能包含多次模型调用，
把多次调用折到一个动作上，才是业务方能用的口径。

—— 数据从哪来 ——
从摄取端读回已上报的 span，只认 `langfuse.observation.type == "generation"` 的。
不从应用进程里顺手记一份，是因为**看板必须和 trace 同源**：
两边各记各的，对不上时你分不清是埋点漏了还是看板算错了。

—— 单价表的三个坑 ——
1. 单位是**每百万 token**（`_per_tokens` = 1000000），不是每千。差 1000 倍。
2. 单价必须从表里查，不能写死在代码里。写死之后调价那天，
   所有历史成本会跟着一起变——这是成本看板最常见的失效方式。
3. 本地模型单价为 0，但**这不等于零成本**：机器折旧与电力要在别处核算。
   看板最常见的误导就是把「没有 API 账单」说成「不花钱」，
   所以下面会把这句话打进报表和终端输出里。
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# 上报到 span 属性里的键名，来自 Langfuse SDK v4 的 OTel 语义约定。
ATTR_TYPE = "langfuse.observation.type"
ATTR_MODEL = "langfuse.observation.model.name"
ATTR_USAGE = "langfuse.observation.usage_details"
ATTR_ACTION = "langfuse.observation.metadata.business_action"
ATTR_CASE = "langfuse.observation.metadata.case_id"


def fetch_spans(ingest: str) -> list[dict]:
    with urllib.request.urlopen(ingest.rstrip("/") + "/_spans", timeout=15) as resp:
        return json.load(resp)


def call_cost(input_tokens: int, output_tokens: int, price: dict, per_tokens: int) -> float:
    """按单价表算一次调用的成本。

    不做四舍五入。看板上显示几位小数是展示层的事，存下来的数必须是原值——
    先round 再累加，几百次调用之后总额就和账单对不上了。
    """
    return input_tokens * price["input"] / per_tokens + output_tokens * price["output"] / per_tokens


def build_report(spans: list[dict], pricing: dict) -> dict:
    per = pricing["_per_tokens"]
    models = pricing["models"]
    actions = pricing["business_actions"]

    # 按开始时间排序，让看板的行序和调用的实际发生顺序一致。
    gens = sorted(
        (s for s in spans if str(s["attributes"].get(ATTR_TYPE, "")).lower() == "generation"),
        key=lambda s: s.get("start_ns") or 0,
    )

    calls: list[dict] = []
    unknown_models: set[str] = set()
    for s in gens:
        a = s["attributes"]
        model = a.get(ATTR_MODEL)
        usage = a.get(ATTR_USAGE) or "{}"
        if isinstance(usage, str):
            usage = json.loads(usage)
        it = int(usage.get("input", 0) or 0)
        ot = int(usage.get("output", 0) or 0)
        price = models.get(model)
        if price is None:
            # 不静默跳过：单价表里没有的模型，说明表过期了或者上报的模型名
            # 和表对不上。悄悄漏算比报错更危险——看板会显示一个偏低的数字，
            # 而没人知道它偏低。
            unknown_models.add(str(model))
            continue
        calls.append({
            "trace_id": s["trace_id"],
            "span_id": s["span_id"],
            "case_id": a.get(ATTR_CASE),
            "action": a.get(ATTR_ACTION) or "(未标注)",
            "model": model,
            "input_tokens": it,
            "output_tokens": ot,
            "cost_cny": call_cost(it, ot, price, per),
            "latency_ms": round(((s.get("end_ns") or 0) - (s.get("start_ns") or 0)) / 1e6, 1),
        })

    # 看板包含单价表里声明的**全部**业务动作，哪怕这次一次都没跑到。
    # 只列跑到的动作，会让「某个动作彻底没被调用」这种故障看不出来。
    by_action: dict[str, dict] = {
        name: {"calls": 0, "total_cny": 0.0, "avg_cny": 0.0,
               "input_tokens": 0, "output_tokens": 0,
               "desc": meta.get("desc", "")}
        for name, meta in actions.items()
    }
    for c in calls:
        row = by_action.setdefault(
            c["action"],
            {"calls": 0, "total_cny": 0.0, "avg_cny": 0.0,
             "input_tokens": 0, "output_tokens": 0, "desc": ""},
        )
        row["calls"] += 1
        row["total_cny"] += c["cost_cny"]
        row["input_tokens"] += c["input_tokens"]
        row["output_tokens"] += c["output_tokens"]
    for row in by_action.values():
        # avg 由 total/calls 现算，不单独累加——两个数各算各的就会对不上。
        row["avg_cny"] = row["total_cny"] / row["calls"] if row["calls"] else 0.0

    used = sorted({c["model"] for c in calls})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": pricing.get("_currency", "CNY"),
        "per_tokens": per,
        "models_used": used,
        "unit_prices": {m: models[m] for m in used},
        "calls": calls,
        "by_action": by_action,
        "totals": {
            "calls": len(calls),
            "total_cny": sum(c["cost_cny"] for c in calls),
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
        },
        "unknown_models": sorted(unknown_models),
        "caveat": ("本地模型单价为 0 不等于零成本：机器折旧与电力应在别处核算。"
                   "单价表须标注取数日期并定期从厂商定价页同步。"),
    }


def print_board(report: dict) -> None:
    cur = report["currency"]
    print(f"== 每次调用 ==（单价单位：{cur}/{report['per_tokens']:,} token）")
    print(f"{'用例':<6}{'业务动作':<20}{'模型':<22}{'in':>7}{'out':>7}{'成本('+cur+')':>14}")
    for c in report["calls"]:
        print(f"{str(c['case_id'] or '-'):<6}{c['action']:<20}{c['model']:<22}"
              f"{c['input_tokens']:>7}{c['output_tokens']:>7}{c['cost_cny']:>14.8f}")

    print(f"\n== 按业务动作聚合 ==")
    print(f"{'业务动作':<20}{'调用次数':>10}{'总成本('+cur+')':>16}{'单次均价('+cur+')':>18}")
    for name, v in report["by_action"].items():
        print(f"{name:<20}{v['calls']:>10}{v['total_cny']:>16.8f}{v['avg_cny']:>18.8f}")

    if report["unknown_models"]:
        print(f"\n[warn] 单价表里没有这些模型，其调用未计入成本：{report['unknown_models']}")
    if all(p["input"] == 0 and p["output"] == 0 for p in report["unit_prices"].values()) \
            and report["unit_prices"]:
        print(f"\n[注] 本次全部调用的 API 成本为 0（本地推理）。{report['caveat']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Lab-08 成本归因与看板")
    ap.add_argument("--ingest", required=True, help="Langfuse / mock 摄取端地址")
    ap.add_argument("--pricing", required=True, help="单价表 json")
    ap.add_argument("--out", required=True, help="产物目录")
    args = ap.parse_args()

    with open(args.pricing, encoding="utf-8") as f:
        pricing = json.load(f)

    report = build_report(fetch_spans(args.ingest), pricing)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cost_report.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print_board(report)
    t = report["totals"]
    print(f"\n报表已写出：{out_path}")
    print(f"actions={len(report['by_action'])} calls={t['calls']} total_cny={t['total_cny']:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
