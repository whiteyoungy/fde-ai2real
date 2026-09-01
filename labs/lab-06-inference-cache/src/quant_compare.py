# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""量化档位对比：qwen2.5:0.5b（q4）vs qwen2.5:0.5b-instruct-q8_0（q8）。

    python3 -m src.quant_compare
    → 对比表 + models=2

比三件事：**延迟、体积、同一 prompt 下的输出**。前两件是数字，第三件不是——
量化档位的取舍从来不是「快多少」单独能回答的，得看输出还能不能用。

这里只用本地已有的两个档位，不下载新模型。本书写作环境磁盘只剩几个 GB，
而且换档位就意味着上面所有延迟数字作废，多拉一个模型对结论没有增量。

**这两个 tag 确实是同一个 checkpoint 的两个量化档**，值得先核实再下结论：
`qwen2.5:0.5b` 看名字像基座 tag，实际 Ollama 的 qwen2.5 默认 tag 就是
instruct 版。实测两者 `/api/show` 返回的 parameter_size 都是 494.03M、
chat template 逐字节相同、system prompt 相同，只有 quantization_level 一个
是 Q4_K_M 一个是 Q8_0。所以这张表里的输出差异可以归因到量化，不掺「模型不同」。

（这条本来写反了：先按 tag 名字猜成「q4 基座 / q8 instruct」，核实模板和
参数量之后才改过来。量化对比最容易翻车的就是这一步——两个 tag 名字差一截，
到底是不是同一份权重，必须查 `ollama show`，不能靠 tag 名字推断。）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import common
from . import serve

PROMPTS = [
    "用一句话回答：年假没休完怎么办？",
    "用一句话回答：ERR-4021 和 ERR-4012 是同一个故障码吗？",
]

REPEATS = 2


def model_size(models: list[dict], name: str) -> int:
    for m in models:
        if m.get("name") == name or m.get("model") == name:
            return int(m.get("size") or 0)
    return 0


def measure(model: str, backend: str) -> dict:
    serve.warmup(model, backend)
    lat: list[float] = []
    tps: list[float] = []
    outputs: list[str] = []
    for prompt in PROMPTS:
        for i in range(REPEATS):
            r = serve.generate(prompt, model=model, backend=backend)
            lat.append(r["latency_ms"])
            tps.append(r["tps"])
            if i == 0:
                outputs.append(r["text"])
    return {
        "model": model,
        "runs": len(lat),
        "p50_ms": common.percentile(lat, 50),
        "mean_ms": sum(lat) / len(lat),
        "tps": sum(tps) / len(tps),
        "outputs": outputs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="量化档位对比")
    ap.add_argument("--backend", default=serve.DEFAULT_BACKEND)
    ap.add_argument("--out", default=str(common.RESULTS))
    args = ap.parse_args()

    try:
        installed = serve.list_models(args.backend)
    except Exception as exc:  # noqa: BLE001 — 后端不可达时要把原因打出来
        print(f"取模型列表失败：{exc}", file=sys.stderr)
        return 1

    targets = [("q4", serve.MODEL_Q4), ("q8", serve.MODEL_Q8)]
    rows = []
    for tier, name in targets:
        size = model_size(installed, name)
        if size == 0:
            print(
                f"本地没有 {name}，请先 ollama pull {name}", file=sys.stderr
            )
            return 1
        r = measure(name, args.backend)
        r["tier"] = tier
        r["size_mb"] = round(size / 1e6, 1)
        rows.append(r)

    base = rows[0]
    lines = []
    lines.append(f"{'档位':<6}{'模型':<30}{'体积MB':>9}{'P50 ms':>9}{'tok/s':>8}{'相对 q4':>9}")
    for r in rows:
        ratio = r["p50_ms"] / base["p50_ms"] if base["p50_ms"] else 0.0
        lines.append(
            f"{r['tier']:<6}{r['model']:<30}{r['size_mb']:>9.1f}"
            f"{r['p50_ms']:>9.0f}{r['tps']:>8.1f}{ratio:>8.2f}x"
        )
    for i, prompt in enumerate(PROMPTS):
        lines.append(f"\nprompt: {prompt}")
        for r in rows:
            lines.append(f"  [{r['tier']}] {r['outputs'][i]}")
    lines.append(
        "\n口径：两个 tag 的 parameter_size(494.03M)、chat template、system prompt 完全相同，"
        "只有 quantization_level 分别是 Q4_K_M 与 Q8_0——是同一 checkpoint 的两个量化档，"
        "输出差异可归因到量化。tag 名字看不出这一点，须以 ollama show 为准。"
    )
    table = "\n".join(lines)
    print(table, flush=True)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "quant_compare.json").write_text(
        json.dumps(
            {
                "models": len(rows),
                "prompts": PROMPTS,
                "repeats": REPEATS,
                "rows": rows,
                "caveat": "已核实两 tag 为同一 checkpoint 的两个量化档（Q4_K_M / Q8_0），"
                "parameter_size、chat template、system prompt 均相同",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"models={len(rows)} "
        f"size_ratio={rows[1]['size_mb'] / rows[0]['size_mb']:.2f}x "
        f"p50_ratio={rows[1]['p50_ms'] / rows[0]['p50_ms']:.2f}x",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
