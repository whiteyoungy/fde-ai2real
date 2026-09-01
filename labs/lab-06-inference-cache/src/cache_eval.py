# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""命中率 / 误命中率评测，含纯阈值对照组。

用法：
    python3 -m src.cache_eval --pairs fixtures/cache_pairs.jsonl
        → mode=api|nokey hit=7/10 false_hit=0/12
    python3 -m src.cache_eval --pairs fixtures/cache_pairs.jsonl --naive
        → mode=naive hit=7/10 false_hit=4/12

**对照组与实验组共用同一个阈值**（common.SIM_THRESHOLD），差别只在有没有
第 2 层护栏和第 3 层裁判。这一点是第 5 项验收的全部意义：只看误命中的话，
把阈值调到 0.99 也能让它变 0，但那时缓存等于没有（README 实测 0.94 时
10 条同义改写只认出 1 条，**却仍然有一次误命中**）。同阈值对比才能证明
是护栏在起作用，不是阈值在起作用。

每对用例用一个**全新的、只有一条记录的** SemanticCache：
夹具里 t01 与 f02 的 base 是同一句「年假没休完怎么办」，共用一个缓存会让
两条用例互相污染，测出来的就不是「这一对该不该命中」了。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import cache as cachelib
from . import common


def evaluate(pairs: list[dict], naive: bool = False) -> dict:
    use_guard = not naive
    use_judge = not naive

    # 先把写入侧（base）一次性编码好，省一点时间。编码是模型的确定性输出，
    # 缓存它不会影响任何判定；判定结果一律不缓存。
    # probe 不预编码——查询侧走 use_cache=False 现算，与压测口径保持一致。
    common.encode([p["base"] for p in pairs])

    rows = []
    hit_total = hit_ok = 0
    miss_total = false_hit = 0
    mode = "naive"

    for p in pairs:
        c = cachelib.SemanticCache(use_guard=use_guard, use_judge=use_judge)
        mode = c.mode
        c.put(p["base"], f"【{p['base']}】的标准答复")
        d = c.lookup(p["probe"])
        rows.append(
            {
                "id": p["id"],
                "expect": p["expect"],
                "base": p["base"],
                "probe": p["probe"],
                "hit": d.hit,
                "score": round(d.score, 4),
                "stage": d.stage,
                "judged": d.judged,
                "correct": d.hit == (p["expect"] == "hit"),
                "why": p.get("why", ""),
            }
        )
        if p["expect"] == "hit":
            hit_total += 1
            hit_ok += int(d.hit)
        else:
            miss_total += 1
            false_hit += int(d.hit)

    return {
        "mode": mode,
        "threshold": common.SIM_THRESHOLD,
        "hit": hit_ok,
        "hit_total": hit_total,
        "false_hit": false_hit,
        "miss_total": miss_total,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="语义缓存命中率 / 误命中率评测")
    ap.add_argument("--pairs", default=str(common.FIXTURES / "cache_pairs.jsonl"))
    ap.add_argument("--backend", default=None, help="兼容 verify.sh；本探针不打后端")
    ap.add_argument("--naive", action="store_true", help="纯阈值对照组：关掉护栏与裁判")
    ap.add_argument("--out", default=str(common.RESULTS))
    args = ap.parse_args()

    pairs = common.load_jsonl(pathlib.Path(args.pairs))
    res = evaluate(pairs, naive=args.naive)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"cache_eval_{res['mode']}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    common.flush()

    # 明细走 stderr：verify.sh 把 stdout 整段塞进结果行，多行会糊掉；
    # 而 stderr 被收进 results/*.err，失败时正好能直接看。
    wrong = [r for r in res["rows"] if not r["correct"]]
    for r in res["rows"]:
        mark = "OK " if r["correct"] else "XX "
        print(
            f"{mark}{r['id']} expect={r['expect']:<4} hit={str(r['hit']):<5} "
            f"score={r['score']:.3f} stage={r['stage']:<15} "
            f"{r['base']} || {r['probe']}",
            file=sys.stderr,
        )
    print(f"-- 判错 {len(wrong)} 条，阈值 {res['threshold']}", file=sys.stderr)

    print(
        f"mode={res['mode']} hit={res['hit']}/{res['hit_total']} "
        f"false_hit={res['false_hit']}/{res['miss_total']} "
        f"threshold={res['threshold']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
