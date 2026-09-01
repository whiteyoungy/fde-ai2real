# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""把 1241 篇文档灌进 Qdrant。

用法：python3 -m src.index --qdrant http://127.0.0.1:16333
输出：indexed=1241
"""
from __future__ import annotations

import argparse

from qdrant_client import QdrantClient, models

from . import common


def build_client(url: str) -> QdrantClient:
    return QdrantClient(url=url, timeout=120)


def ensure_collection(client: QdrantClient, name: str) -> None:
    # 1.19 起 recreate_collection 已弃用，显式删了重建更清楚，也保证评测可复现。
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(
            size=common.VECTOR_DIM, distance=models.Distance.COSINE),
    )
    # doc_id / codes 建 keyword 索引：三分法 Step 1 要用 scroll() 做精确扫描，
    # 走的是 payload 过滤而不是向量检索，有索引才不至于每次全表扫。
    for field in ("doc_id", "codes", "category"):
        client.create_payload_index(
            collection_name=name, field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD)


def index_all(url: str, collection: str = common.COLLECTION) -> int:
    docs = common.load_docs()
    vecs = common.encode([common.doc_text(d) for d in docs], "docs")
    client = build_client(url)
    ensure_collection(client, collection)

    points = []
    for i, (d, v) in enumerate(zip(docs, vecs)):
        payload = {
            "doc_id": d["id"],
            "title": d["title"],
            "body": d["body"],
            "category": d.get("category", ""),
            # 文档自带的标识符，Step 1 精确扫描按它过滤
            "codes": common.extract_ids(common.doc_text(d)),
        }
        # 数据污染的判据就是这个字段：有它说明本文已被新版取代
        if d.get("superseded_by"):
            payload["superseded_by"] = d["superseded_by"]
        points.append(models.PointStruct(id=i, vector=v.tolist(), payload=payload))

    for start in range(0, len(points), 256):
        client.upsert(collection_name=collection,
                      points=points[start:start + 256], wait=True)

    return client.count(collection_name=collection, exact=True).count


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qdrant", required=True)
    ap.add_argument("--collection", default=common.COLLECTION)
    args = ap.parse_args()
    n = index_all(args.qdrant, args.collection)
    print(f"indexed={n} collection={args.collection} dim={common.VECTOR_DIM} "
          f"model={common.MODEL_NAME}")


if __name__ == "__main__":
    main()
