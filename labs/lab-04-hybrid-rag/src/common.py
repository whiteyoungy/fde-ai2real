# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""共用组件：语料加载、中文分词、向量编码（带磁盘缓存）。

这里只放"两条检索路都要用"的东西。刻意不放任何检索逻辑——
检索在 retrieve.py，评测在 evaluate.py，诊断在 diagnose.py。

缓存策略：只缓存 embedding（模型的确定性输出），**不缓存任何检索结果**。
缓存 key 里带了模型名和全部待编码文本的哈希，语料一改缓存自动失效，
不会出现"改了语料却在用旧向量"这种把评测做假的情况。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
RESULTS = ROOT / "results"
CACHE = RESULTS / "cache"

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
VECTOR_DIM = 512
COLLECTION = "lab04_kb"

# RRF 必须在各路 top-K 截断之后融合。TOPK 之外的文档不获得任何贡献。
# 若改成对完整排序做 RRF，混合会永远夹在两个基线之间（见 README）。
TOPK = 50
RRF_K = 60
EVAL_K = 5          # Recall@K 的 K
RERANK_DEPTH = 20   # 重排只碰候选集头部，生产上同样只对 top-20 做

# 标识符形态：ERR-4012 / BX-07A / INC-20777 / CRM-88 / OA-2314
ID_RE = re.compile(r"[A-Za-z]{2,5}-\d{1,6}[A-Za-z]?")

_PUNCT = set("，。、；：？！“”‘’（）【】「」《》·—…〈〉％"
             " \t\r\n,.;:?!()[]{}<>\"'`~@#$%^&*_+-=|\\/")


def load_jsonl(path: pathlib.Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_docs() -> list[dict]:
    return load_jsonl(FIXTURES / "docs.jsonl")


def load_queries() -> list[dict]:
    return load_jsonl(FIXTURES / "queries.jsonl")


def doc_text(d: dict) -> str:
    """索引与编码统一用这一段文本，避免两路看到的内容不一致。"""
    return f"{d['title']}\n{d['body']}"


def extract_ids(text: str) -> list[str]:
    """抽出文本里的标识符，统一小写。BM25 与 Step 1 精确扫描都用它。"""
    return sorted({m.lower() for m in ID_RE.findall(text)})


def tokenize(text: str) -> list[str]:
    """中文 BM25 的分词。

    不分词的 BM25 在中文上几乎等于没用——rank_bm25 只会按空格切，
    整句变成一个 token，除了标点什么都对不上。

    额外把 `ERR-4021` 这类标识符整体也塞进 token 流：jieba 会把它切成
    ['err', '-', '4021']，切开后 `err` 这个词在 5 篇故障码文档里都出现，
    区分度全靠 `4021`。补一个整体 token 是防御性的。

    **实测更正**：在本 Lab 语料上补这个整体 token 对 Recall@5 毫无影响
    （加与不加都是 54/59，分类别数字也逐项相同）——因为 `4021` 这样的
    数字串本身已经足够唯一。留着它是为了换语料时不塌，不要以为它在贡献分数。
    """
    import jieba  # 延迟导入：diagnose 的部分路径用不到，省一次词典加载

    low = text.lower()
    toks = [t for t in ID_RE.findall(low)]
    for t in jieba.lcut(low):
        t = t.strip()
        if not t or all(ch in _PUNCT for ch in t):
            continue
        toks.append(t)
    return toks


_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def encode(texts: list[str], tag: str) -> np.ndarray:
    """编码并缓存。normalize_embeddings=True 让余弦等价于内积。"""
    texts = list(texts)
    key = hashlib.sha1(
        ("\x00".join([MODEL_NAME, tag, *texts])).encode("utf-8")).hexdigest()[:16]
    path = CACHE / f"emb-{tag}-{key}.npy"
    if path.exists():
        try:
            arr = np.load(path)
            if arr.shape == (len(texts), VECTOR_DIM):
                return arr
        except Exception:
            pass  # 缓存坏了就重算，不要让评测因为缓存挂掉
    vecs = get_model().encode(
        texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    vecs = np.asarray(vecs, dtype=np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(path, vecs)
    return vecs
