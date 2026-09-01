# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""推理后端封装。

本 Lab 用 Ollama 而不是 vLLM——原因写在 README 开头，简述是本书写作环境
无 GPU、2 核 3GB，vLLM 的 wheel 与 torch 依赖装不下也起不来。语义缓存要教
的东西与后端无关，但**所有延迟数字都与后端强绑定**，换成 vLLM 后这里量出
来的每一个毫秒都作废，必须在你自己的卡上重量。

只用标准库发 HTTP：requirements.txt 里没有 requests，而 urllib 足够了。
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_BACKEND = os.environ.get("OLLAMA", "http://127.0.0.1:11434")

# 两个本地量化档位。q4 是默认档，q8 用于第 7 项对比。
MODEL_Q4 = "qwen2.5:0.5b"
MODEL_Q8 = "qwen2.5:0.5b-instruct-q8_0"
DEFAULT_MODEL = MODEL_Q4

# CPU 上单次推理约 3.9 秒 / 18 token。压测要跑 40 次冷请求，num_predict
# 每多 8 个 token 就多花 1.5 秒 × 40 次 = 一分钟。这里刻意压到 24：
# 本 Lab 量的是「缓存省掉了一次推理」，不是「生成质量」。
GEN_TOKENS = 24


class BackendError(RuntimeError):
    pass


def _post(url: str, payload: dict, timeout: float) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 把响应体带出来，否则只有一个状态码
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise BackendError(f"HTTP {exc.code} {url}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BackendError(f"连接失败 {url}: {exc}") from exc


def version(backend: str = DEFAULT_BACKEND, timeout: float = 5.0) -> str:
    try:
        with urllib.request.urlopen(f"{backend}/api/version", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("version", "?")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise BackendError(f"取版本失败 {backend}: {exc}") from exc


def list_models(backend: str = DEFAULT_BACKEND, timeout: float = 10.0) -> list[dict]:
    with urllib.request.urlopen(f"{backend}/api/tags", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")).get("models", [])


def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    backend: str = DEFAULT_BACKEND,
    num_predict: int = GEN_TOKENS,
    timeout: float = 180.0,
) -> dict:
    """一次非流式生成。返回 text / latency_ms / eval_count / tps。

    latency_ms 用客户端墙钟量，不用 Ollama 自报的 total_duration——客户端
    等的是墙钟，包含排队与网络，那才是用户感受到的延迟。
    """
    t0 = time.perf_counter()
    data = _post(
        f"{backend}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "5m",  # 不加载完就卸载，否则每次都付一遍加载成本
            "options": {"num_predict": num_predict, "temperature": 0, "seed": 7},
        },
        timeout,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0
    eval_count = int(data.get("eval_count") or 0)
    eval_ns = int(data.get("eval_duration") or 0)
    return {
        "text": (data.get("response") or "").strip(),
        "latency_ms": latency_ms,
        "eval_count": eval_count,
        "tps": (eval_count / (eval_ns / 1e9)) if eval_ns else 0.0,
        "model": model,
    }


def warmup(model: str = DEFAULT_MODEL, backend: str = DEFAULT_BACKEND) -> None:
    """把权重先加载进内存。不做这一步，第一次请求会把模型加载时间算进延迟，
    冷/温对比就掺进了一个和缓存无关的大常数。"""
    try:
        generate("你好", model=model, backend=backend, num_predict=1)
    except BackendError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Ollama 推理后端探针")
    ap.add_argument("--backend", default=DEFAULT_BACKEND)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--probe", action="store_true", help="打印单次基线延迟")
    ap.add_argument("--prompt", default="用一句话说明年假没休完怎么处理。")
    args = ap.parse_args()

    try:
        ver = version(args.backend)
    except BackendError as exc:
        print(f"后端不可达：{exc}", flush=True)
        return 1

    if not args.probe:
        r = generate(args.prompt, model=args.model, backend=args.backend)
        print(r["text"])
        return 0

    warmup(args.model, args.backend)
    r = generate(args.prompt, model=args.model, backend=args.backend)
    print(
        f"backend=ollama version={ver} model={args.model} "
        f"baseline_ms={r['latency_ms']:.0f} tokens={r['eval_count']} "
        f"tps={r['tps']:.1f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
