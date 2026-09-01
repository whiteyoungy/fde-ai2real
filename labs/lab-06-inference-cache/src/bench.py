# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""压测：冷跑（缓存关闭）与温跑（缓存开启）对比 P50/P95/QPS/命中率。

    python3 -m src.bench --n 40
    → cold_p50_ms=.. cold_p95_ms=.. warm_p50_ms=.. warm_p95_ms=.. qps=.. cache_hit_rate=..

## 请求流怎么构造

真实的客服流量不是 40 条互不相同的问题——那样任何缓存都不会命中，压出来的
「缓存没收益」是被流量构造决定的，不是被缓存决定的。这里按真实 FAQ 的形态
构造：**少数几个高频话题，每个话题有若干种问法，长尾里混入全新问题。**

具体是 7 个话题（每个话题两种问法：原句 + 已实测相似度 >0.85 的同义改写）
按 Zipf 式的偏斜分布抽 38 条，再加 2 条**全新**问题，固定随机种子打散。
冷跑与温跑用的是**同一条流**（同一个 seed 生成一次，两遍复用）。

## 「温」是什么意思

温跑 = 缓存已经热了的稳态，不是「把缓存打开然后从空的开始跑」。所以测量前
有一个不计入统计的预热阶段：把 7 条 FAQ 原句喂进去（未命中 → 真推理 → 入库），
再把 7 条改写各过一遍（命中原句 → 走一次裁判 → **不入库**）。

命中时不写入新条目是刻意的：写入会让缓存被同一件事的各种问法撑爆，而且下次
同样的改写会退化成字符串精确命中，第 2、3 层永远不会被执行到。真实的语义缓存
只在未命中时写入。

预热阶段自己的 P95 也一并打印（emptycache_p95_ms）——**把缓存打开的那一刻
延迟并不会下降**，收益全部来自后面的命中。这个数字值得单独看一眼。

## 关于 n=40 时的 P95

最近秩 P95 取排序后第 38 个样本，也就是说 **40 个请求里最多容忍 2 个慢请求**，
第 3 个慢请求就会把 P95 顶回未命中的量级。所以这条流的重复率必须做到 95%
才能让 P95 有肉眼可见的下降。这不是把测试调软，这是 P95 在小样本上的分辨力
本身就这么粗——真要看缓存对长尾的影响，样本量得上千，或者改看 P50 与均值
（两者本文件都打印了）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time

from . import cache as cachelib
from . import common
from . import serve

# 7 个高频话题。改写句全部来自 fixtures/cache_pairs.jsonl 里 expect=hit 且
# 实测相似度 >0.85 的那几对，不是现编的——现编的改写可能压根过不了第 1 层，
# 那时命中率低就成了流量的问题而不是缓存的问题。
TOPICS: list[tuple[str, str]] = [
    ("年假没休完怎么办", "没休完的年假该怎么处理"),
    ("会议室怎么预订", "如何预订会议室"),
    ("加班能调休吗", "加班可以换调休吗"),
    ("试用期多长", "试用期一般是多久"),
    ("离职证明多久能开", "离职证明需要多长时间办好"),
    ("怎么申请居家办公", "在家办公要如何申请"),
    ("体检什么时候预约", "健康检查的预约时间是什么时候"),
]

# 长尾里的全新问题。实测与上面 7 个话题的最高相似度分别是 0.508 / 0.524，
# 远在阈值之下，一定未命中——它们的作用是让温跑里仍然有真实的推理成本，
# 而不是把命中率刷成 100%。
NOVEL = ["园区停车位怎么申请", "食堂午餐几点开始供应"]

ZIPF_WEIGHTS = [0.28, 0.20, 0.15, 0.12, 0.10, 0.08, 0.07]


def build_stream(n: int, seed: int = 20250808) -> list[str]:
    rng = random.Random(seed)
    n_novel = min(len(NOVEL), max(0, n - len(TOPICS)))
    n_faq = n - n_novel
    stream: list[str] = []
    for _ in range(n_faq):
        t = rng.choices(range(len(TOPICS)), weights=ZIPF_WEIGHTS, k=1)[0]
        # 七成用原句、三成用改写：真实流量里「标准问法」总是占多数，
        # 但改写足够多到能把第 2、3 层压出成本。
        stream.append(TOPICS[t][0] if rng.random() < 0.7 else TOPICS[t][1])
    stream.extend(NOVEL[:n_novel])
    rng.shuffle(stream)
    return stream


def _answer(question: str, model: str, backend: str) -> str:
    r = serve.generate(
        f"你是公司行政助手。用一句话回答：{question}", model=model, backend=backend
    )
    return r["text"]


def run_pass(
    stream: list[str],
    backend: str,
    model: str,
    cache: cachelib.SemanticCache | None,
) -> dict:
    """跑一遍请求流。cache=None 表示缓存关闭（冷跑）。"""
    lat: list[float] = []
    hits = 0
    t_start = time.perf_counter()
    for q in stream:
        t0 = time.perf_counter()
        if cache is not None:
            d = cache.lookup(q)
            if d.hit:
                hits += 1
                lat.append((time.perf_counter() - t0) * 1000.0)
                continue
            ans = _answer(q, model, backend)
            cache.put(q, ans)  # 只在未命中时写入
        else:
            _answer(q, model, backend)
        lat.append((time.perf_counter() - t0) * 1000.0)
    wall = time.perf_counter() - t_start
    return {
        "n": len(stream),
        "p50_ms": common.percentile(lat, 50),
        "p95_ms": common.percentile(lat, 95),
        "mean_ms": sum(lat) / len(lat) if lat else 0.0,
        "max_ms": max(lat) if lat else 0.0,
        "wall_s": wall,
        "qps": len(stream) / wall if wall else 0.0,
        "hits": hits,
        "hit_rate": hits / len(stream) if stream else 0.0,
        "latencies_ms": [round(x, 1) for x in lat],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="语义缓存压测")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--backend", default=serve.DEFAULT_BACKEND)
    ap.add_argument("--model", default=serve.DEFAULT_MODEL)
    ap.add_argument("--out", default=str(common.RESULTS))
    args = ap.parse_args()

    stream = build_stream(args.n)
    distinct = len(set(stream))

    # 先把权重加载进内存。不预热，第一次请求会把模型加载时间算进冷跑的
    # 第一个样本，冷/温对比里就掺进一个和缓存完全无关的大常数。
    serve.warmup(args.model, args.backend)

    print(
        f"流量：{args.n} 条请求 / {distinct} 种不同问法 "
        f"（{len(TOPICS)} 个话题 × 两种问法 + {len(NOVEL)} 条全新问题）",
        file=sys.stderr,
    )

    # ── 冷跑：缓存关闭，同一条流 ────────────────────────────────
    cold = run_pass(stream, args.backend, args.model, None)
    print(
        f"冷跑（缓存关闭）：p50={cold['p50_ms']:.0f}ms p95={cold['p95_ms']:.0f}ms "
        f"qps={cold['qps']:.2f} 耗时 {cold['wall_s']:.0f}s",
        file=sys.stderr,
    )

    # ── 预热：不计入统计 ───────────────────────────────────────
    warm_cache = cachelib.SemanticCache()
    prewarm_stream = [t[0] for t in TOPICS] + [t[1] for t in TOPICS]
    prewarm = run_pass(prewarm_stream, args.backend, args.model, warm_cache)
    prewarm_judge_calls = warm_cache.stats.judge_calls
    print(
        f"预热（缓存开启但为空）：p50={prewarm['p50_ms']:.0f}ms "
        f"p95={prewarm['p95_ms']:.0f}ms 命中 {prewarm['hits']}/{prewarm['n']}"
        "  ← 打开缓存的那一刻延迟并不会降",
        file=sys.stderr,
    )

    # ── 温跑：缓存已热，同一条流 ───────────────────────────────
    warm_cache.stats = cachelib.Stats()
    warm = run_pass(stream, args.backend, args.model, warm_cache)
    print(
        f"温跑（缓存已热）：p50={warm['p50_ms']:.0f}ms p95={warm['p95_ms']:.0f}ms "
        f"qps={warm['qps']:.2f} 命中 {warm['hits']}/{warm['n']} "
        f"裁判调用 {warm_cache.stats.judge_calls} 次",
        file=sys.stderr,
    )

    payload = {
        "n": args.n,
        "distinct_questions": distinct,
        "mode": warm_cache.mode,
        "threshold": warm_cache.threshold,
        "percentile_method": "nearest-rank（n=40 时 P95 取第 38 个样本，最多容忍 2 个慢请求）",
        "cold": cold,
        "prewarm": prewarm,
        "warm": warm,
        "prewarm_judge_calls": prewarm_judge_calls,
        "warm_stats": {
            "judge_calls": warm_cache.stats.judge_calls,
            "blocked_by_guard": warm_cache.stats.blocked_by_guard,
            "blocked_by_judge": warm_cache.stats.blocked_by_judge,
            "stage_ms": {k: round(v, 1) for k, v in warm_cache.stats.stage_ms.items()},
        },
        "stream": stream,
    }
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bench.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    common.flush()

    print(
        f"cold_p50_ms={cold['p50_ms']:.0f} cold_p95_ms={cold['p95_ms']:.0f} "
        f"warm_p50_ms={warm['p50_ms']:.0f} warm_p95_ms={warm['p95_ms']:.0f} "
        f"qps={warm['qps']:.2f} cache_hit_rate={warm['hit_rate']:.2f} "
        f"emptycache_p95_ms={prewarm['p95_ms']:.0f} "
        f"cold_qps={cold['qps']:.2f} mode={warm_cache.mode}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
