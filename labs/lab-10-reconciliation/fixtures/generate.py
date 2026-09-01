#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""生成 Lab-10 的两套系统台账、事件流与期望结果。

第 16 章 16.4 节给对账智能体定了三步（隔离 → 根因诊断 → 起草补偿），
并点名了三类根因：**时区换算、乱序到达、数据模型不对齐**。
这份夹具就按这三类各造一条，外加一组对照。

对照组是这份夹具里最要紧的部分。三条注入之外还有四条**看起来可疑、
实际完全正常**的事务：

  - N-3001 事件确实乱序到达，但下游按事件时间排序后终态正确 —— 乱序 ≠ 不一致
  - N-3002 金额为负（红冲退款），两边都正确记为负 —— 负数 ≠ 异常
  - N-3003 跨零点发生，但两边时区处理一致 —— 跨天 ≠ 时区问题
  - N-3004 两边金额字段单位不同但换算后一致 —— 单位不同 ≠ 不对齐

没有这组对照，一个"凡是看着奇怪就报异常"的智能体也能拿满分。
而在真实的财务对账场景里，误报的代价很具体：每一条误报都要一个人去查，
查完发现没事。误报率高的对账系统，最后的结局是没人看它的告警。

用法：python3 fixtures/generate.py
产出：fixtures/recon.db（两套系统台账）、fixtures/events.jsonl（事件流）、
      fixtures/expected.json（期望的检出结果与根因）
"""
import json
import pathlib
import sqlite3

OUT = pathlib.Path(__file__).parent
DB = OUT / "recon.db"

# ── 建库 ───────────────────────────────────────────────────────
if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)
con.executescript("""
-- 系统 A：订单系统的台账。金额单位为分，时间带时区偏移。
CREATE TABLE sys_a_txn (
    txn_id      TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,      -- ISO8601，带 +08:00 偏移
    book_date   TEXT NOT NULL       -- 入账日，按北京时间取 date
);

-- 系统 B：财务台账。金额单位为分，时间为「本地时间」但不带偏移标记。
CREATE TABLE sys_b_txn (
    txn_id      TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,      -- ISO8601，无偏移，约定为北京时间
    book_date   TEXT NOT NULL
);

-- 隔离表：被判定为不一致的事务进这里，防止继续参与后续状态计算。
-- 对账智能体只写这张表，不碰上面两张——这是 16.4 节说的那道人工闸门。
CREATE TABLE quarantine (
    txn_id      TEXT PRIMARY KEY,
    root_cause  TEXT NOT NULL,
    detail      TEXT,
    detected_at TEXT
);
""")

A, B, EVENTS, EXPECT = [], [], [], {}


def pair(txn, a, b):
    A.append((txn, *a))
    B.append((txn, *b))


def ev(txn, seq, kind, status, amount_cents, ts, source):
    """一条事件。seq 是它被写入流的顺序，ts 是业务上真实发生的时间。

    seq 与 ts 不一致，就是「乱序到达」。
    """
    EVENTS.append({"txn_id": txn, "seq": seq, "kind": kind, "status": status,
                   "amount_cents": amount_cents, "occurred_at": ts, "source": source})


# ══ 注入一：时区换算 ══════════════════════════════════════════
# A 记的是北京时间 2026-04-01 07:30（4 月），B 把同一时刻的 UTC 值
# 当成本地时间存了下来（3 月 31 日 23:30）。金额一分不差，但**跨了月**。
# 月末结账时这一笔在 A 算 4 月、在 B 算 3 月，两边月报对不上。
pair("T-2001",
     ("SETTLED", 458000, "2026-04-01T07:30:00+08:00", "2026-04-01"),
     ("SETTLED", 458000, "2026-03-31T23:30:00",       "2026-03-31"))
ev("T-2001", 1, "settle", "SETTLED", 458000, "2026-04-01T07:30:00+08:00", "sys_a")
ev("T-2001", 2, "settle", "SETTLED", 458000, "2026-03-31T23:30:00", "sys_b")
EXPECT["T-2001"] = {"root_cause": "timezone",
                    "why": "同一时刻，A 按 +08:00 记为 4/1，B 把 UTC 值当本地时间记为 3/31，跨月"}

# ══ 注入二：乱序到达 ══════════════════════════════════════════
# PAID 先于 CREATED 到达。B 的消费者按到达顺序处理，CREATED 后到就把
# 状态覆盖回了 CREATED，这笔付款在财务侧从未入账。
pair("T-2002",
     ("PAID", 129900, "2026-04-02T10:15:00+08:00", "2026-04-02"),
     ("CREATED", 0,   "2026-04-02T10:15:00",       "2026-04-02"))
ev("T-2002", 1, "pay",    "PAID",    129900, "2026-04-02T10:15:00+08:00", "sys_a")
ev("T-2002", 2, "create", "CREATED", 0,      "2026-04-02T10:12:00+08:00", "sys_a")
EXPECT["T-2002"] = {"root_cause": "out_of_order",
                    "why": "PAID(10:15) 先于 CREATED(10:12) 到达，下游按到达顺序覆盖，终态回退为 CREATED"}

# ══ 注入三：数据模型不对齐 ════════════════════════════════════
# A 的 128000 是「分」（1280 元）。B 接入时误把它当「元」直接写进
# amount_cents，成了 12800000 分。差 100 倍，且方向一致，最像"系统性错误"。
pair("T-2003",
     ("SETTLED", 128000,   "2026-04-03T14:00:00+08:00", "2026-04-03"),
     ("SETTLED", 12800000, "2026-04-03T14:00:00",       "2026-04-03"))
ev("T-2003", 1, "settle", "SETTLED", 128000,   "2026-04-03T14:00:00+08:00", "sys_a")
ev("T-2003", 2, "settle", "SETTLED", 12800000, "2026-04-03T14:00:00", "sys_b")
EXPECT["T-2003"] = {"root_cause": "model_mismatch",
                    "why": "A 的单位是分，B 接入时当成元又写进分字段，相差 100 倍"}

# ══ 对照组：看着可疑，实际全对，一条都不许报 ══════════════════

# N-3001：事件确实乱序，但下游按事件时间排序处理，终态正确。
# 乱序到达本身不是异常，处理错了才是。
pair("N-3001",
     ("PAID", 66600, "2026-04-04T09:00:00+08:00", "2026-04-04"),
     ("PAID", 66600, "2026-04-04T09:00:00",       "2026-04-04"))
ev("N-3001", 1, "pay",    "PAID",    66600, "2026-04-04T09:00:00+08:00", "sys_a")
ev("N-3001", 2, "create", "CREATED", 0,     "2026-04-04T08:58:00+08:00", "sys_a")

# N-3002：红冲退款，金额为负。两边都正确记为负。
# 负数不等于异常——Lab-01 里已经踩过一次"金额必须为正"的坑。
pair("N-3002",
     ("REFUNDED", -45000, "2026-04-05T11:20:00+08:00", "2026-04-05"),
     ("REFUNDED", -45000, "2026-04-05T11:20:00",       "2026-04-05"))
ev("N-3002", 1, "refund", "REFUNDED", -45000, "2026-04-05T11:20:00+08:00", "sys_a")
ev("N-3002", 2, "refund", "REFUNDED", -45000, "2026-04-05T11:20:00", "sys_b")

# N-3003：发生在 23:58，跨天边缘，但两边时区处理一致，入账日相同。
# 跨天不等于时区问题。
pair("N-3003",
     ("SETTLED", 88800, "2026-04-06T23:58:00+08:00", "2026-04-06"),
     ("SETTLED", 88800, "2026-04-06T23:58:00",       "2026-04-06"))
ev("N-3003", 1, "settle", "SETTLED", 88800, "2026-04-06T23:58:00+08:00", "sys_a")
ev("N-3003", 2, "settle", "SETTLED", 88800, "2026-04-06T23:58:00", "sys_b")

# N-3004：金额很大且是整百万，看着像单位错了，实际两边一致。
pair("N-3004",
     ("SETTLED", 100000000, "2026-04-07T16:40:00+08:00", "2026-04-07"),
     ("SETTLED", 100000000, "2026-04-07T16:40:00",       "2026-04-07"))
ev("N-3004", 1, "settle", "SETTLED", 100000000, "2026-04-07T16:40:00+08:00", "sys_a")
ev("N-3004", 2, "settle", "SETTLED", 100000000, "2026-04-07T16:40:00", "sys_b")

# ── 再补一批完全普通的事务，让对账不是在 7 条上做 ────────────
for i in range(1, 41):
    t = f"N-40{i:02d}"
    amt = 10000 + i * 137
    day = f"2026-04-{(i % 28) + 1:02d}"
    pair(t, ("SETTLED", amt, f"{day}T12:00:00+08:00", day),
            ("SETTLED", amt, f"{day}T12:00:00", day))
    ev(t, 1, "settle", "SETTLED", amt, f"{day}T12:00:00+08:00", "sys_a")

con.executemany("INSERT INTO sys_a_txn VALUES (?,?,?,?,?)", A)
con.executemany("INSERT INTO sys_b_txn VALUES (?,?,?,?,?)", B)
con.commit()
con.close()

EVENTS.sort(key=lambda e: (e["txn_id"], e["seq"]))
(OUT / "events.jsonl").write_text(
    "\n".join(json.dumps(e, ensure_ascii=False) for e in EVENTS) + "\n")
(OUT / "expected.json").write_text(
    json.dumps({"inconsistent": EXPECT,
                "must_not_flag": ["N-3001", "N-3002", "N-3003", "N-3004"]},
               ensure_ascii=False, indent=2) + "\n")

print(f"台账 A/B 各 {len(A)} 条；事件 {len(EVENTS)} 条")
print(f"  注入不一致 {len(EXPECT)} 条：" + "、".join(f"{k}({v['root_cause']})" for k, v in EXPECT.items()))
print(f"  对照组（一条都不许报）4 条：N-3001 乱序但正确、N-3002 负数退款、"
      f"N-3003 跨天但时区一致、N-3004 大额但两边一致")
