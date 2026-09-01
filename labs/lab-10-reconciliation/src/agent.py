#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""对账智能体：隔离 → 根因诊断 → 起草补偿。

用法：
    python3 -m src.agent --bootstrap 127.0.0.1:19092 --db fixtures/recon.db --out results
输出：
    consumed=54 flagged=3 quarantined=3 executed=0
产物：
    results/report.json        每条不一致的根因、证据与补偿草案
    results/compensation.sql   可执行的补偿脚本草案——**只落盘，不执行**

## 这道闸门是用代码守住的，不是靠自觉

第 16 章 16.4 节：「『起草』和『执行』之间必须隔一道人工闸门。」

`executed=0` 是自报的，没有约束力。这里的约束力来自 `sqlite3.set_authorizer`：
连接上挂了一个授权回调，对 `sys_a_txn` / `sys_b_txn` 的任何 INSERT/UPDATE/DELETE/
DROP/ALTER 一律返回 `SQLITE_DENY`。也就是说，即便后来有人在这个文件里写下
`con.executescript(open('results/compensation.sql').read())`，它也会当场抛
`sqlite3.DatabaseError: not authorized`，而不是悄悄把财务台账改了。

写一道自己也能绕过的闸门，等于没写。这个回调只允许写 `quarantine` 一张表。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sqlite3
import sys
import time
import uuid

from kafka import KafkaConsumer

from . import diagnose, llm

DEFAULT_TOPIC = "txn-events"

# 业务表：智能体只读。补偿由人复核后另行执行。
PROTECTED_TABLES = {"sys_a_txn", "sys_b_txn"}
WRITE_ACTIONS = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                 sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE}


def _authorizer(action: int, arg1: str | None, arg2: str | None,
                db_name: str | None, trigger: str | None) -> int:
    """人工闸门的机器实现：业务表只读，写操作一律拒绝。"""
    if action in WRITE_ACTIONS and (arg1 or "") in PROTECTED_TABLES:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.set_authorizer(_authorizer)
    return con


def load_ledger(con: sqlite3.Connection, table: str) -> dict[str, dict]:
    return {r["txn_id"]: dict(r) for r in con.execute(f"SELECT * FROM {table}")}


# ── 事件流 ─────────────────────────────────────────────────────
def consume(bootstrap: str, topic: str, group: str | None,
            idle_ms: int = 8000, attempts: int = 3) -> list[dict]:
    """把 topic 从头读一遍。

    默认每次运行用一个新的消费者组：这个智能体是**全量重算**语义（每一轮都
    重建全部事务的执行图），不是增量消费。沿用旧组会读到 0 条，
    看起来像 Kafka 坏了，实际是 offset 已经在末尾。要复现增量行为传 --group。
    """
    records: list[dict] = []
    last_err: Exception | None = None
    for attempt in range(attempts):
        gid = group or f"recon-agent-{uuid.uuid4().hex[:8]}"
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap,
                group_id=gid,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                consumer_timeout_ms=idle_ms,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
        except Exception as exc:  # noqa: BLE001 — broker 刚起来时可能还连不上
            last_err = exc
            time.sleep(2 * (attempt + 1))
            continue
        try:
            records = [msg.value for msg in consumer]
            if records:
                consumer.commit()  # 让 offset 正常推进，别留个没提交的组
        finally:
            consumer.close(autocommit=False)
        if records:
            return records
        last_err = RuntimeError(f"消费者组 {gid} 在 {idle_ms}ms 内没读到任何事件")
        time.sleep(2 * (attempt + 1))
    if last_err and not records:
        print(f"警告：{last_err}", file=sys.stderr)
    return records


# ── 产物 ───────────────────────────────────────────────────────
SQL_HEADER = """\
-- 对账补偿脚本（草案）
-- 生成时间：{now}
-- 生成者：src/agent.py（自动起草）
--
-- 这份脚本没有被执行过，也不该由生成它的程序执行。
-- 第 16 章 16.4 节：「『起草』和『执行』之间必须隔一道人工闸门——财务台账数据的
-- 写操作一旦执行错误，回滚成本远高于多等复核的几分钟。」
--
-- 复核要点：
--   1. 根因判得对不对？三类根因的补偿方向完全不同，判错了这份脚本就是错的。
--   2. 影响面对不对？下面每条语句都带 WHERE txn_id，不应出现无条件 UPDATE。
--   3. 执行前后各存一次库快照，确认只有列出的 {n} 条记录被改动。
--
-- 确认无误后由复核人执行，例如：
--   sqlite3 fixtures/recon.db < results/compensation.sql
"""


def write_compensation(path: pathlib.Path, findings: list[dict]) -> None:
    lines = [SQL_HEADER.format(now=dt.datetime.now().isoformat(timespec="seconds"),
                               n=len(findings))]
    for f in findings:
        lines.append(f"\n-- [{f['txn_id']}] 根因：{f['root_cause']}")
        for seg in _wrap_comment(f["detail"]):
            lines.append(f"--   {seg}")
        # 双系统事件时间线也抄进脚本：只看 SQL 的复核人不该被迫另开一份 report.json
        if f["timeline"]:
            lines.append("--   事件时间线（seq=到达顺序，occurred_at=业务时间）：")
            for e in f["timeline"]:
                lines.append(f"--     seq={e['seq']} {e['kind']} {e['status']} "
                             f"{e['amount_cents']} @{e['occurred_at']} ({e['source']})")
        lines.append(f"--   A: {f['sys_a']}")
        lines.append(f"--   B: {f['sys_b']}")
        lines.extend(f["compensation_sql"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _wrap_comment(text: str, width: int = 46) -> list[str]:
    """把说明按宽度切成注释行。中文按字符宽度切就够了，不引 textwrap 的英文断词。"""
    return [text[i:i + width] for i in range(0, len(text), width)] or [""]


def write_quarantine(con: sqlite3.Connection, findings: list[dict]) -> int:
    """写隔离表。先清空本智能体上一轮的判定，再整批写入。

    对账是全量重算语义：这一轮的结论就是全部结论。不清空的话，
    上一轮判过、这一轮已经不成立的记录会留在表里变成幽灵告警；
    而反复运行也会撞主键。
    """
    now = dt.datetime.now().isoformat(timespec="seconds")
    con.execute("DELETE FROM quarantine")
    con.executemany(
        "INSERT OR REPLACE INTO quarantine (txn_id, root_cause, detail, detected_at) "
        "VALUES (?,?,?,?)",
        [(f["txn_id"], f["root_cause"], f["quarantine_detail"], now) for f in findings])
    con.commit()
    return con.execute("SELECT count(*) FROM quarantine").fetchone()[0]


# ── 主流程 ─────────────────────────────────────────────────────
def run(args: argparse.Namespace) -> int:
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    events = consume(args.bootstrap, args.topic, args.group, args.idle_ms)
    by_txn: dict[str, list[dict]] = {}
    for e in events:
        by_txn.setdefault(e["txn_id"], []).append(e)

    con = open_db(args.db)
    a_rows = load_ledger(con, "sys_a_txn")
    b_rows = load_ledger(con, "sys_b_txn")

    # ① 检出：只看终态是否一致（判据见 diagnose.compare 的注释）
    diffs = diagnose.compare(a_rows, b_rows)

    use_model = llm.has_key()
    findings: list[dict] = []
    for d in diffs:
        txn_id = d["txn_id"]
        a, b = d["a"], d["b"]
        evs = by_txn.get(txn_id, [])
        # ② 根因诊断：规则说了算
        dg = diagnose.diagnose(a, b, evs) if a and b else {
            "root_cause": "unknown", "detail": "一侧缺失记录，需人工介入", "evidence": {}}
        # ③ 起草补偿：只生成文本
        sql = diagnose.compensation_sql(txn_id, a, b, dg["root_cause"]) if a and b else []

        # 时间线对每一条都给，不只给乱序那一条。16.6 节记的坑：只给根因分类
        # （「时区漂移」四个字）而不摆出双系统事件时间线，复核人没有能力独立
        # 验证这个判断，只能盲信或全部打回——两种结果都违背设计初衷。
        timeline = [{"seq": e["seq"], "kind": e["kind"], "status": e["status"],
                     "amount_cents": e["amount_cents"],
                     "occurred_at": e["occurred_at"], "source": e["source"]}
                    for e in sorted(evs, key=lambda x: x["seq"])]

        f = {
            "txn_id": txn_id,
            "root_cause": dg["root_cause"],
            "diff_fields": d["fields"],
            "detail": dg["detail"],
            "evidence": dg["evidence"],
            "sys_a": a,
            "sys_b": b,
            "timeline": timeline,
            "event_count": len(evs),
            "compensation_sql": sql,
            # 16.5 节的 ReconciliationReport.requires_human_approval：硬编码为真，
            # 不是一个可以被上游逻辑或配置项关掉的默认值
            "requires_human_approval": True,
            "executed": False,
        }
        if use_model:
            f.update(llm.enrich(txn_id, a, b, evs, dg["root_cause"], dg["detail"], sql))
        # 模型的说明只是复述，落进隔离表的仍是规则依据 + 模型说明（若有）
        f["quarantine_detail"] = " ｜ ".join(
            x for x in (dg["detail"], f.get("explanation")) if x)
        findings.append(f)

    quarantined = write_quarantine(con, findings)
    write_compensation(out / "compensation.sql", findings)

    mode = f"rule+model({llm.MODEL})" if use_model else "rule"
    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "bootstrap": args.bootstrap,
        "topic": args.topic,
        "consumed": len(events),
        "ledger_rows": len(a_rows),
        "flagged": len(findings),
        "quarantined": quarantined,
        "executed": 0,
        "diagnosis_mode": mode,
        "gate": ("起草 ≠ 执行：本智能体只写 quarantine 表，补偿 SQL 只落盘不执行；"
                 "业务表的写操作由 sqlite3 授权回调在连接层拒绝"),
        "root_cause_counts": {rc: sum(1 for f in findings if f["root_cause"] == rc)
                              for rc in sorted({f["root_cause"] for f in findings})},
        "findings": findings,
    }
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    con.close()
    print(f"consumed={len(events)} flagged={len(findings)} "
          f"quarantined={quarantined} executed=0")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="事件流后台对账智能体")
    ap.add_argument("--bootstrap", default="127.0.0.1:19092")
    ap.add_argument("--db", default="fixtures/recon.db")
    ap.add_argument("--out", default="results")
    ap.add_argument("--topic", default=DEFAULT_TOPIC)
    ap.add_argument("--group", default=None, help="消费者组；默认每次新建（全量重算语义）")
    ap.add_argument("--idle-ms", type=int, default=8000,
                    help="多久读不到新事件就认为读完了")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
