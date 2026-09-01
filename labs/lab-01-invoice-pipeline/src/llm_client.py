# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""双路径 LLM 客户端：有 DEEPSEEK_API_KEY 用 DeepSeek，没有就降级到本机 Ollama。

硬要求（任务书原文，不可替换）：

    if os.getenv("DEEPSEEK_API_KEY"):
        base_url, model, key = os.getenv("DEEPSEEK_BASE_URL"), "deepseek-chat", os.environ["DEEPSEEK_API_KEY"]
    else:
        base_url, model, key = "http://127.0.0.1:11434/v1", "qwen2.5:0.5b", "ollama"

Key 只从环境变量读取，本文件（以及本 Lab 任何文件）都不写入真实 key。
写法参考 `../lab-05-evals/src/llm_client.py`。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    """从仓库根目录 .env 加载环境变量（只做一次）。找不到 dotenv 包也不报错——
    这种情况下直接依赖调用方已经设置好的进程环境变量。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        _ENV_LOADED = True
        return
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        candidate = Path(__file__).resolve().parents[2] / ".env"
        if candidate.exists():
            dotenv_path = str(candidate)
    if dotenv_path:
        load_dotenv(dotenv_path)
    _ENV_LOADED = True


@dataclass(frozen=True)
class ClientConfig:
    base_url: str
    model: str
    api_key: str
    using_deepseek: bool


def get_client_config() -> ClientConfig:
    """双路径判定逻辑（任务书原文，不可替换）。"""
    _ensure_env_loaded()
    if os.getenv("DEEPSEEK_API_KEY"):
        base_url = os.getenv("DEEPSEEK_BASE_URL")
        model = "deepseek-chat"
        api_key = os.environ["DEEPSEEK_API_KEY"]
        return ClientConfig(base_url=base_url, model=model, api_key=api_key, using_deepseek=True)
    base_url = "http://127.0.0.1:11434/v1"
    model = "qwen2.5:0.5b"
    api_key = "ollama"
    return ClientConfig(base_url=base_url, model=model, api_key=api_key, using_deepseek=False)


def has_key() -> bool:
    _ensure_env_loaded()
    return bool(os.getenv("DEEPSEEK_API_KEY"))


class LLMClient:
    """对 openai SDK 的极薄封装，统一走双路径配置。抛异常交给调用方处理（不吞错）。"""

    def __init__(self, config: Optional[ClientConfig] = None, timeout: float = 45.0):
        self.config = config or get_client_config()
        self._client = None
        self.timeout = timeout

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.timeout,
            )
        return self._client

    def chat(self, prompt: str, *, system: Optional[str] = None, temperature: float = 0.0,
              max_tokens: int = 300) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        return content or ""


def default_client() -> LLMClient:
    return LLMClient(get_client_config())
