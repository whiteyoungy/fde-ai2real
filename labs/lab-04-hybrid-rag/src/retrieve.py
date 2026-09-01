# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""四种检索：BM25 / 纯向量 / RRF 混合 / 交叉编码器重排。

三个约定，改动会直接影响验收数值：

1. **RRF 在各路 top-K 截断后融合**（TOPK=50）。落在 K 之外的文档不获得
   任何贡献。若对完整排序做 RRF，一个 BM25 排第 1、向量排第 800 的文档
   仍能靠 BM25 那一项挤掉向量排第 1 的正确答案，混合就永远夹在两个基线中间。
2. **BM25 必须先分词**（common.tokenize，jieba + 标识符整体 token）。
3. **Qdrant 1.19 没有 search()/recommend()**，一律用 query_points()；
   过滤参数在 query_points 里叫 query_filter，在 scroll 里叫 scroll_filter。
"""
from __future__ import annotations

import numpy as np
from qdrant_client import QdrantClient, models

from . import common


def rrf(rank_lists: list[list[str]], k: int = common.RRF_K,
        topk: int = common.TOPK) -> list[str]:
    """Reciprocal Rank Fusion：score(d) = Σ 1 / (k + rank_i(d))。

    好处是不需要把 BM25 分数和余弦分数归一化到同一量纲——只用名次。
    """
    scores: dict[str, float] = {}
    for lst in rank_lists:
        for rank, doc_id in enumerate(lst[:topk], start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    # 并列时按 doc_id 定序，保证多次运行结果完全一致
    return [d for d, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


class Retrievers:
    """三路检索器。docs 只加载一次，BM25 索引懒构建。"""

    def __init__(self, client: QdrantClient, collection: str = common.COLLECTION,
                 docs: list[dict] | None = None):
        self.client = client
        self.collection = collection
        self.docs = docs if docs is not None else common.load_docs()
        self.by_id = {d["id"]: d for d in self.docs}
        self._bm25 = None
        self._reranker = None
        self._codes: dict[str, set[str]] | None = None

    # ── BM25 ────────────────────────────────────────────────────────
    @property
    def bm25(self):
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi
            corpus = [common.tokenize(common.doc_text(d)) for d in self.docs]
            self._bm25 = BM25Okapi(corpus)
        return self._bm25

    def search_bm25(self, query: str, topk: int = common.TOPK) -> list[str]:
        scores = self.bm25.get_scores(common.tokenize(query))
        # -score 升序 + 原始下标做次序键，保证并列时的顺序稳定
        order = sorted(range(len(self.docs)), key=lambda i: (-scores[i], i))
        return [self.docs[i]["id"] for i in order[:topk]]

    # ── 纯向量 ──────────────────────────────────────────────────────
    def search_vector(self, qvec: np.ndarray, topk: int = common.TOPK,
                      query_filter: models.Filter | None = None) -> list[str]:
        res = self.client.query_points(
            collection_name=self.collection,
            query=np.asarray(qvec, dtype=np.float32).tolist(),
            limit=topk,
            with_payload=True,
            query_filter=query_filter,   # 注意：scroll() 那边叫 scroll_filter
        )
        return [p.payload["doc_id"] for p in res.points]

    # ── RRF 混合 ────────────────────────────────────────────────────
    def search_hybrid(self, query: str, qvec: np.ndarray,
                      topk: int = common.TOPK) -> list[str]:
        lex = self.search_bm25(query, topk)
        vec = self.search_vector(qvec, topk)
        return rrf([lex, vec], common.RRF_K, topk)

    def search(self, kind: str, query: str, qvec: np.ndarray,
               topk: int = common.TOPK) -> list[str]:
        if kind == "bm25":
            return self.search_bm25(query, topk)
        if kind == "vector":
            return self.search_vector(qvec, topk)
        if kind == "hybrid":
            return self.search_hybrid(query, qvec, topk)
        raise ValueError(f"未知检索器：{kind}")

    # ── 重排 ────────────────────────────────────────────────────────
    @property
    def reranker(self):
        """交叉编码器。加载失败（无模型/无网络）时返回 None，走降级重排。"""
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(
                    "BAAI/bge-reranker-base", max_length=384)
            except Exception:
                self._reranker = False
        return self._reranker or None

    @property
    def codes(self) -> dict[str, set[str]]:
        if self._codes is None:
            self._codes = {d["id"]: set(common.extract_ids(common.doc_text(d)))
                           for d in self.docs}
        return self._codes

    def exact_id_pin(self, query: str, candidates: list[str]) -> str | None:
        """查询里的标识符在候选集中有且只有一篇精确命中时，返回那一篇。

        这是重排的护栏。实测过"不加护栏、直接让交叉编码器重排 top-20"：
        semantic 类 MRR 0.594 → 0.938（大涨），但 buried_id 类 1.000 → 0.921，
        总账 0.9449 → 0.9379，**净变差**。原因和稠密向量失手是同一个：
        1200 篇复盘报告措辞几乎一致，交叉编码器同样分不开 INC-20777 和
        INC-20778，反而把 BM25 已经排对的第一名挤下去。

        词面精确命中是这一类查询上不可替代的决定性证据，任何软打分模型
        都不该覆盖它——这条护栏不是为了凑数字，是这个语料的真实性质。
        """
        q_ids = set(common.extract_ids(query))
        if not q_ids:
            return None
        hits = [d for d in candidates if q_ids & self.codes.get(d, set())]
        return hits[0] if len(hits) == 1 else None

    def rerank(self, query: str, candidates: list[str],
               depth: int = common.RERANK_DEPTH) -> tuple[list[str], str]:
        """对混合检索的头部候选重排，返回 (新顺序, 档位说明)。

        重排延迟高：交叉编码器要对每个 (query, doc) 单独前向一次，
        生产上只对 top-20 做，再往下收益追不上延迟。这里再省一层——
        标识符已经给出决定性证据时直接跳过重排，交叉编码器只用在
        真正需要语义判断的模糊查询上（本 Lab 59 条里只有 14 条走模型）。
        """
        head, tail = candidates[:depth], candidates[depth:]
        if not head:
            return candidates, "none"

        pinned = self.exact_id_pin(query, head)
        if pinned is not None:
            return ([pinned] + [d for d in head if d != pinned] + tail,
                    "exact-id-pin")

        ce = self.reranker
        if ce is not None:
            pairs = [(query, common.doc_text(self.by_id[d])[:384]) for d in head]
            scores = ce.predict(pairs, batch_size=8, show_progress_bar=False)
            tier = "cross-encoder(BAAI/bge-reranker-base)"
        else:
            scores = [self._lexical_rerank_score(query, d) for d in head]
            tier = "heuristic(lexical-overlap)"

        order = sorted(range(len(head)), key=lambda i: (-float(scores[i]), i))
        return [head[i] for i in order] + tail, tier

    def _lexical_rerank_score(self, query: str, doc_id: str) -> float:
        """降级重排：标识符精确命中 + 词面覆盖率。可解释，但不如交叉编码器。"""
        q_tok = set(common.tokenize(query))
        d_tok = set(common.tokenize(common.doc_text(self.by_id[doc_id])))
        q_ids = set(common.extract_ids(query))
        d_ids = set(common.extract_ids(common.doc_text(self.by_id[doc_id])))
        cover = len(q_tok & d_tok) / max(1, len(q_tok))
        return cover + 2.0 * len(q_ids & d_ids)


def scroll_all(client: QdrantClient, collection: str,
               scroll_filter: models.Filter | None = None,
               limit: int = 256) -> list[dict]:
    """分页 scroll 出全部 payload。三分法 Step 1 用它做精确扫描。

    刻意不带向量、也不做 ANN 检索——Step 1 要确认的是"内容存在与否"这个
    更底层的事实，如果这一步也走检索，检索本身失效时就会被误判成"没有材料"。
    """
    out, offset = [], None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,   # 注意：query_points() 那边叫 query_filter
            limit=limit, offset=offset,
            with_payload=True, with_vectors=False,
        )
        out.extend(p.payload for p in points)
        if offset is None:
            break
    return out
