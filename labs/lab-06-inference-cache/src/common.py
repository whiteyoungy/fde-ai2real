# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""共用组件：路径、阈值常量、标识符正则、向量编码（带磁盘缓存）。

缓存策略照抄 Lab-04 的规矩：**只缓存 embedding**（模型对同一段文本的确定性
输出），绝不缓存任何判定结果——不缓存相似度比较的结论、不缓存护栏结果、
更不缓存第 3 层裁判的「是/否」。理由很直接：把判定缓存了，评测就变成在读
上一次的答案，第 4、5 项验收会在实现被改坏之后仍然「通过」。

缓存 key 里带模型名与文本本身的哈希，换 embedding 模型或改夹具，缓存自动
失效，不会出现「改了夹具却在用旧向量」。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import threading

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
RESULTS = ROOT / "results"

EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
EMBED_DIM = 512

# ── 阈值 ────────────────────────────────────────────────────────────────
# 0.85 是在 fixtures/cache_pairs.jsonl 上标定出来的：纯阈值方案在这里是
# 命中 7/10、误命中 4/12。它不是一个「好」阈值——README 的表已经证明这份
# 夹具上不存在好阈值（应命中的最低 0.651 < 不该命中的最高 0.954，两组完全
# 重叠）。选 0.85 是因为它把召回留在了可用区间，把分辨的活儿交给第 2、3 层。
#
# 换 embedding 模型后这个数字立刻作废，必须重新标定。
SIM_THRESHOLD = float(os.environ.get("SIM_THRESHOLD", "0.85"))

# 三层方案与纯阈值对照组**共用**这一个常量。第 5 项验收防的就是
# 「护栏没起作用，只是对照组阈值调低了」——两组同阈值，差别只在护栏与裁判。

# ── 第 2 层：标识符护栏 ──────────────────────────────────────────────────
# BX-07 / BX-70 / ERR-4021 / ERR-4012 / OA-2314 / OA-3214 这类。
# 护栏的规则是「两个问题里抽出的标识符集合必须完全一致」，不是「相似」。
# BX-07 与 BX-70 编辑距离为 2 却是两张完全不同的单据，任何模糊匹配都是错的。
ID_RE = re.compile(r"[A-Za-z]{2,4}-\d{2,5}[A-Za-z]?")

_LOCK = threading.Lock()
_MODEL = None
_MEM: dict[str, np.ndarray] = {}
_DISK_LOADED = False
_DIRTY = False

EMBED_CACHE = RESULTS / "embed_cache.json"


def extract_ids(text: str) -> frozenset[str]:
    """抽出文本里的标识符，统一大写后去重。"""
    return frozenset(m.upper() for m in ID_RE.findall(text))


def ids_conflict(a: str, b: str) -> bool:
    """第 2 层护栏：两问的标识符集合不完全一致 → 判定不可共用答案。

    注意「两边都没有标识符」时返回 False（放行）——护栏只在有编号可比时
    发声，它管不了「公章 / 合同章」这种没有编号的情形，那是第 3 层的活儿。
    """
    return extract_ids(a) != extract_ids(b)


def load_jsonl(path: pathlib.Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _key(text: str) -> str:
    h = hashlib.sha256()
    h.update(EMBED_MODEL.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:32]


def _load_disk() -> None:
    global _DISK_LOADED
    if _DISK_LOADED:
        return
    _DISK_LOADED = True
    if not EMBED_CACHE.exists():
        return
    try:
        raw = json.loads(EMBED_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if raw.get("model") != EMBED_MODEL:
        return
    for k, v in raw.get("vectors", {}).items():
        vec = np.asarray(v, dtype=np.float32)
        if vec.shape == (EMBED_DIM,):
            _MEM[k] = vec


def flush() -> None:
    """把新算出来的向量落盘。进程退出前调一次即可。"""
    global _DIRTY
    if not _DIRTY:
        return
    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": EMBED_MODEL,
        "vectors": {k: [round(float(x), 6) for x in v] for k, v in _MEM.items()},
    }
    tmp = EMBED_CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(EMBED_CACHE)
    _DIRTY = False


def _model():
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            from sentence_transformers import SentenceTransformer

            _MODEL = SentenceTransformer(EMBED_MODEL)
    return _MODEL


def encode(texts: list[str], use_cache: bool = True) -> np.ndarray:
    """编码为 L2 归一化向量，形状 (n, 512)。归一化后点积即余弦相似度。

    use_cache=False 用于**查询侧**：压测量的是用户感受到的延迟，而线上每一条
    进来的问题都得现算一次 embedding。用缓存里的向量替它，P50 会从 20ms 掉到
    0.2ms——那个数字是测试脚手架造出来的，不是缓存带来的。写入侧（put）仍然
    走缓存，那相当于离线建好的库，本来就不该算进查询延迟。
    """
    global _DIRTY
    if not use_cache:
        vecs = _model().encode(
            list(texts), normalize_embeddings=True, batch_size=16, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32)
    _load_disk()
    missing = [t for t in texts if _key(t) not in _MEM]
    if missing:
        uniq = list(dict.fromkeys(missing))
        vecs = _model().encode(
            uniq, normalize_embeddings=True, batch_size=16, show_progress_bar=False
        )
        for t, v in zip(uniq, np.asarray(vecs, dtype=np.float32)):
            _MEM[_key(t)] = v
        _DIRTY = True
    return np.stack([_MEM[_key(t)] for t in texts])


def encode_one(text: str, use_cache: bool = True) -> np.ndarray:
    return encode([text], use_cache=use_cache)[0]


def percentile(values: list[float], p: float) -> float:
    """最近秩（nearest-rank）分位数：排序后取第 ceil(p/100 * n) 个。

    刻意不用 numpy 的线性插值版本。延迟 SLO 场景下 P95 的含义是「95% 的请求
    不慢于这个数」，最近秩直接对应这句话，且不会插值出一个从未发生过的延迟。
    两种算法在本 Lab 的 40 个样本上会给出不同的 P95，写清楚用的是哪一种，
    比数字本身重要。

    秩必须按 `ceil(p * n / 100)` 算，不能写成 `ceil(p / 100 * n)`。
    后者在 p=95、n=40 时是 `0.95 * 40 = 38.000000000000006`，ceil 之后
    变成 39——P95 悄悄变成了 P97.5，正好把那两个未命中的慢请求圈了进来，
    压测结论直接反过来。整数先乘后除就没有这个问题。
    """
    if not values:
        return 0.0
    s = sorted(values)
    import math

    idx = max(1, math.ceil(p * len(s) / 100.0)) - 1
    return s[min(idx, len(s) - 1)]
