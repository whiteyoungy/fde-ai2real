# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""三路基线对比（Recall@5）与重排效果（MRR）。

用法：
  python3 -m src.evaluate --qdrant URL --out results
      → bm25=N vector=N hybrid=N，并写 results/report.json
  python3 -m src.evaluate --qdrant URL --mode rerank --out results
      → hybrid_mrr=.. rerank_mrr=.. improved=yes，并写 results/report_rerank.json

分类别报告不是装饰。只看总分会被"BM25 一家独大、混合搭便车"蒙混过去——
混合真正成立的前提是两路的失败集不相交，这只能在分类别数字上看出来。
"""
from __future__ import annotations

import argparse
import json
import pathlib

from . import common
from .index import build_client
from .retrieve import Retrievers

MODES = ("bm25", "vector", "hybrid")


def _hit(ranking: list[str], gold: list[str], k: int) -> bool:
    return any(g in ranking[:k] for g in gold)


def _rr(ranking: list[str], gold: list[str]) -> float:
    for i, d in enumerate(ranking, start=1):
        if d in gold:
            return 1.0 / i
    return 0.0


def run(qdrant: str, out: pathlib.Path, collection: str, mode: str) -> None:
    queries = common.load_queries()
    qvecs = common.encode([q["query"] for q in queries], "queries")
    retr = Retrievers(build_client(qdrant), collection)
    out.mkdir(parents=True, exist_ok=True)

    rankings = {m: [] for m in MODES}
    for q, v in zip(queries, qvecs):
        for m in MODES:
            rankings[m].append(retr.search(m, q["query"], v))

    if mode == "rerank":
        _report_rerank(retr, queries, rankings["hybrid"], out)
    else:
        _report_baseline(queries, rankings, out)


def _report_baseline(queries: list[dict], rankings: dict[str, list[list[str]]],
                     out: pathlib.Path) -> None:
    k = common.EVAL_K
    overall = {m: 0 for m in MODES}
    by_kind: dict[str, dict[str, int]] = {}
    per_query = []

    for i, q in enumerate(queries):
        kind = q["kind"]
        slot = by_kind.setdefault(kind, {"n": 0, **{m: 0 for m in MODES}})
        slot["n"] += 1
        row = {"id": q["id"], "kind": kind, "query": q["query"], "gold": q["gold"]}
        for m in MODES:
            hit = _hit(rankings[m][i], q["gold"], k)
            overall[m] += hit
            slot[m] += hit
            row[m] = {"hit": hit, "rank": _rank_of(rankings[m][i], q["gold"])}
        per_query.append(row)

    report = {
        "model": common.MODEL_NAME,
        "collection_size": len(common.load_docs()),
        "n_queries": len(queries),
        "eval_k": k,
        "fusion": {"method": "rrf", "k": common.RRF_K, "topk": common.TOPK},
        "overall": overall,
        "by_kind": by_kind,
        "per_query": per_query,
    }
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    n = len(queries)
    # 这一行是 verify.sh 唯一解析的行。分类别明细**不能**再出现
    # `bm25=` / `vector=` / `hybrid=` 这三个子串——verify.sh 用的是
    # `grep -o 'hybrid=[0-9]*'`，多匹配一次就会拿到多行值，
    # 后面的算术展开直接报语法错，第 4 项会既不判 OK 也不判 FAIL 地消失。
    print(f"bm25={overall['bm25']} vector={overall['vector']} "
          f"hybrid={overall['hybrid']} total={n} metric=recall@{k}")
    print(f"  {'类型':<10} {'条数':>4} {'BM25':>6} {'向量':>6} {'混合':>6}")
    for kind in ("lexical", "semantic", "hybrid", "buried_id"):
        s = by_kind.get(kind)
        if s:
            print(f"  {kind:<12} {s['n']:>4} {s['bm25']:>6} "
                  f"{s['vector']:>6} {s['hybrid']:>6}")


def _rank_of(ranking: list[str], gold: list[str]) -> int:
    for i, d in enumerate(ranking, start=1):
        if d in gold:
            return i
    return -1


def _report_rerank(retr: Retrievers, queries: list[dict],
                   hybrid_rankings: list[list[str]], out: pathlib.Path) -> None:
    """重排只动混合检索候选集的头部顺序，召回集合不变——MRR 才是该看的指标。"""
    rows, h_sum, r_sum = [], 0.0, 0.0
    tiers: dict[str, int] = {}
    for q, hyb in zip(queries, hybrid_rankings):
        reranked, tier = retr.rerank(q["query"], hyb)
        tiers[tier] = tiers.get(tier, 0) + 1
        h_sum += _rr(hyb, q["gold"])
        r_sum += _rr(reranked, q["gold"])
        rows.append({"id": q["id"], "kind": q["kind"], "tier": tier,
                     "hybrid_rank": _rank_of(hyb, q["gold"]),
                     "rerank_rank": _rank_of(reranked, q["gold"])})
    tier = "+".join(f"{k}x{v}" for k, v in sorted(tiers.items()))

    n = len(queries)
    h_mrr, r_mrr = h_sum / n, r_sum / n
    improved = "yes" if r_mrr > h_mrr else "no"
    moved_up = sum(1 for r in rows
                   if 0 < r["rerank_rank"] < r["hybrid_rank"])
    moved_down = sum(1 for r in rows
                     if r["hybrid_rank"] > 0 and r["rerank_rank"] > r["hybrid_rank"])

    (out / "report_rerank.json").write_text(json.dumps({
        "reranker": tier, "depth": common.RERANK_DEPTH,
        "hybrid_mrr": h_mrr, "rerank_mrr": r_mrr, "improved": improved,
        "moved_up": moved_up, "moved_down": moved_down,
        "per_query": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"hybrid_mrr={h_mrr:.4f} rerank_mrr={r_mrr:.4f} improved={improved} "
          f"depth={common.RERANK_DEPTH} reranker={tier} "
          f"up={moved_up} down={moved_down}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qdrant", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--collection", default=common.COLLECTION)
    ap.add_argument("--mode", default="baseline", choices=("baseline", "rerank"))
    args = ap.parse_args()
    run(args.qdrant, pathlib.Path(args.out), args.collection, args.mode)


if __name__ == "__main__":
    main()
