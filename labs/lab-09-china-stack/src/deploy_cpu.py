#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""CPU 降级路径实测部署探针（讲义第 23 章 · 附录 A 的三类缺口之一）。

本 Lab 同时包含三类性质不同的路径：CPU 降级（**能验，本脚本就是验它的**）、
GPU 标准路径（无 GPU，只能给官方文档流程）、昇腾国产算力（无硬件，同上）。
把它们混成一句话带过是不诚实的，所以三者分开处理——能验的必须真验。

实施计划对这条写得很硬：「CPU 路径必须实测跑通」。所以这个脚本**必须真调
本地模型**，桩实现、录制回放、固定返回值都不算数。verify.sh 第 5 项要求
输出里同时出现 ``ok=true`` 和 ``tokens>=1``——tokens 来自 Ollama 返回的
``eval_count``（模型实际生成的 token 数），编不出来。

用法：
    python3 -m src.deploy_cpu --backend http://127.0.0.1:11434
    python3 -m src.deploy_cpu --backend http://127.0.0.1:11434 --model qwen2.5:0.5b

输出最后一行是可被 grep 的机器可读摘要：

    backend=ollama model=qwen2.5:0.5b tokens=42 ok=true

前面的诊断行刻意不含 ``tokens=`` 字样，免得 verify.sh 的
``grep -o 'tokens=[0-9]*' | head -1`` 抓错行——探针的输出格式是要被别人
用 grep 解析的契约，写的时候就得替解析方想一层。

退出码：实测跑通为 0，任何一步失败为 1。
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# 本 Lab 的 CPU 实测档。0.5B 只用于验证部署链路是否跑通，不用于验证效果——
# 这一点在 models.json 里也标了。拿它的回答质量下结论是误用。
PREFERRED_MODELS = ["qwen2.5:0.5b", "qwen2.5:0.5b-instruct-q8_0"]

# 提示词刻意选一个短、确定性高、能看出中文没乱码的问题。目的是验链路，
# 不是验能力，所以不要用需要推理的题目——那会把"链路不通"和"模型答错"
# 两类问题混在一起，排查时分不开。
PROMPT = "用一句话说明什么是私有化部署。"


def _get(url: str, timeout: float):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(url: str, payload: dict, timeout: float):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_models(backend: str, timeout: float) -> list:
    return [m["name"] for m in _get(f"{backend}/api/tags", timeout).get("models", [])]


def choose_model(available: list, requested: str | None) -> str:
    """定选要实测的模型。

    显式指定优先；否则按 PREFERRED_MODELS 的顺序取第一个本地已有的；
    都没有就报错退出——**不下载**。现场机器的磁盘常常是紧的，探针脚本
    偷偷拉一个几 GB 的模型下来是很坏的行为，宁可失败得明确一点。
    """
    if requested:
        if requested not in available:
            raise RuntimeError(
                f"指定的模型 {requested} 不在本地：{available}。"
                f"本探针不会自动下载模型，请先 ollama pull。")
        return requested
    for name in PREFERRED_MODELS:
        if name in available:
            return name
    if available:
        return available[0]
    raise RuntimeError("Ollama 本地没有任何模型，先 ollama pull qwen2.5:0.5b")


def vram_footprint(backend: str, timeout: float):
    """问 Ollama 这次推理到底有没有吃显存。

    这一步不是装饰。"CPU 路径跑通了"这句话要站得住，就得有个东西能证明
    它确实是在 CPU 上跑的，而不是碰巧机器上有卡、悄悄走了 GPU。
    ``/api/ps`` 的 ``size_vram`` 为 0 就是这个证据。

    拿不到就返回 None，如实标"未知"，不猜。
    """
    try:
        procs = _get(f"{backend}/api/ps", timeout).get("models", [])
    except Exception:
        return None
    if not procs:
        return None
    return sum(int(p.get("size_vram") or 0) for p in procs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CPU 路径实测部署探针")
    ap.add_argument("--backend", default="http://127.0.0.1:11434",
                    help="Ollama 服务地址")
    ap.add_argument("--model", default=None, help="指定模型，缺省自动挑本地小模型")
    ap.add_argument("--timeout", type=float, default=120.0, help="单次推理超时（秒）")
    ap.add_argument("--out", default="results", help="实测记录落盘目录")
    args = ap.parse_args(argv)
    backend = args.backend.rstrip("/")

    model = ""
    tokens = 0
    try:
        version = _get(f"{backend}/api/version", 5.0).get("version", "?")
        available = list_models(backend, 10.0)
        model = choose_model(available, args.model)
        print(f"后端 ollama {version} @ {backend}；本地模型 {len(available)} 个，"
              f"本次实测 {model}")

        t0 = time.time()
        # stream=False：一次拿完整响应，省得在探针里处理分片。
        # 这里不设 temperature=0 之外的任何花样——探针要的是链路可复现。
        resp = _post(f"{backend}/api/generate", {
            "model": model,
            "prompt": PROMPT,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 64},
        }, args.timeout)
        elapsed = time.time() - t0

        text = (resp.get("response") or "").strip()
        # eval_count = 模型实际生成的 token 数。这是"真的调了模型"的凭据，
        # 桩实现伪造不出来（也不该去伪造）。
        tokens = int(resp.get("eval_count") or 0)
        prompt_tokens = int(resp.get("prompt_eval_count") or 0)
        if tokens < 1 or not text:
            raise RuntimeError(
                f"模型返回了空结果（eval_count={tokens}，response 长度 "
                f"{len(text)}）——链路没跑通，不能算通过")

        vram = vram_footprint(backend, 5.0)
        if vram is None:
            vram_desc = "未知（/api/ps 未返回，无法据此断言算力位置）"
        elif vram == 0:
            vram_desc = "0 字节，权重全部驻留内存，确认走的是 CPU 推理"
        else:
            vram_desc = (f"{vram / 1024 ** 3:.2f}GB —— 注意：本次推理占用了显存，"
                         f"说明后端把权重卸载到了 GPU，这条记录不能当作"
                         f"纯 CPU 路径的实测数据")

        print(f"提示词 {prompt_tokens} token，生成 {tokens} 个 token，"
              f"耗时 {elapsed:.2f}s，约 {tokens / elapsed:.1f} tok/s")
        print(f"显存占用：{vram_desc}")
        print(f"模型回答：{text[:120]}")

        record = {
            "backend": "ollama",
            "backend_url": backend,
            "backend_version": version,
            "model": model,
            "prompt": PROMPT,
            "response_excerpt": text[:200],
            "prompt_tokens": prompt_tokens,
            "eval_tokens": tokens,
            "elapsed_s": round(elapsed, 3),
            "tokens_per_s": round(tokens / elapsed, 2),
            "vram_bytes": vram,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "note": ("本记录来自真实调用 Ollama /api/generate 的一次实测，"
                     "eval_tokens 为模型实际生成的 token 数。"
                     "0.5B 档位只用于验证部署链路是否跑通，不用于验证效果。"),
        }
        try:
            import pathlib
            out = pathlib.Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "cpu_deploy.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        except OSError as e:
            # 落盘失败不该让"实测跑通了"这个结论翻车，如实提示即可。
            print(f"（实测记录落盘失败，不影响本次结论：{e}）")

    except Exception as e:
        print(f"backend=ollama model={model or '-'} tokens={tokens} ok=false")
        print(f"失败原因：{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"backend=ollama model={model} tokens={tokens} ok=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
