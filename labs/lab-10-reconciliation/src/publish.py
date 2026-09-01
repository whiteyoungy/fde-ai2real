#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""把事件流灌进 Kafka。

用法：
    python3 -m src.publish --bootstrap 127.0.0.1:19092 --events fixtures/events.jsonl
输出：
    published=54 topic=txn-events

为什么不是直接 diff 两张表：`T-2002` 的根因（乱序到达）在台账上只表现为
「状态不一致」，判不出为什么。要判出来必须回到事件流里看 `seq`（到达顺序）
与 `occurred_at`（业务时间）的错位——这是这个 Lab 需要真 Kafka 的唯一理由。

因此这里有一条硬约束：**topic 只能有一个分区**。多分区下同一 txn 的事件可能
落到不同分区，消费者拿到的相对顺序就不再是写入顺序，「到达顺序」这个信号本身
就被破坏了。生产环境的等价做法是按 `txn_id` 做 key 分区（同 key 同分区），
本文件两条都做了：单分区 + key=txn_id。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from kafka import KafkaAdminClient, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError

DEFAULT_TOPIC = "txn-events"


def ensure_topic(bootstrap: str, topic: str, timeout_ms: int = 10000) -> None:
    """建 topic。已存在就当成功——重复运行是常态，不是错误。

    不依赖 broker 的 auto.create.topics：自动建出来的 topic 分区数由 broker 配置
    决定，上面说的单分区约束就管不住了。
    """
    admin = KafkaAdminClient(bootstrap_servers=bootstrap, request_timeout_ms=timeout_ms)
    try:
        admin.create_topics([NewTopic(name=topic, num_partitions=1, replication_factor=1)])
    except TopicAlreadyExistsError:
        pass
    except KafkaError as exc:  # 已存在的另一种报法（不同版本行为不一致）
        if "TopicExists" not in type(exc).__name__ and "already exists" not in str(exc):
            raise
    finally:
        admin.close()


def load_events(path: pathlib.Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def publish(bootstrap: str, events_path: pathlib.Path, topic: str) -> int:
    events = load_events(events_path)
    ensure_topic(bootstrap, topic)

    producer = KafkaProducer(
        bootstrap_servers=bootstrap,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        acks="all",
        retries=5,
        linger_ms=5,
    )
    try:
        futures = [producer.send(topic, key=e["txn_id"], value=e) for e in events]
        producer.flush(timeout=30)
        for fut in futures:  # 不看 future 就等于没确认写进去
            fut.get(timeout=30)
    finally:
        producer.close(timeout=10)
    return len(events)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把事件流灌进 Kafka")
    ap.add_argument("--bootstrap", default="127.0.0.1:19092")
    ap.add_argument("--events", default="fixtures/events.jsonl")
    ap.add_argument("--topic", default=DEFAULT_TOPIC)
    args = ap.parse_args(argv)

    path = pathlib.Path(args.events)
    if not path.exists():
        print(f"事件流文件不存在：{path}（先跑 python3 fixtures/generate.py）", file=sys.stderr)
        return 2

    # Kafka 刚起来的头几秒里 metadata 可能还没稳定，重试几次比一次失败好判读
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            n = publish(args.bootstrap, path, args.topic)
            print(f"published={n} topic={args.topic}")
            return 0
        except Exception as exc:  # noqa: BLE001 — 最外层要给出可读的失败原因
            last_err = exc
            time.sleep(2 * (attempt + 1))
    print(f"投递失败：{type(last_err).__name__}: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
