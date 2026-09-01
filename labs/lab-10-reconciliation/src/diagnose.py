#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""对账的判据与补偿模板：纯函数，不碰数据库、不碰网络。

这里是整个 Lab 的判断力所在，两件事必须分开看：

**检出**（`compare`）：只看两套系统的**终态**是否一致——金额、状态、入账日、
以及归一到同一时刻后的发生时间。不看「像不像有问题」。
这样一来对照组自然全部落在检出之外：乱序到达（N-3001）终态是对的、
负数退款（N-3002）两边都是负的、跨天（N-3003）两边入账日相同、
大额（N-3004）两边一样大。**判据落在终态是否一致上，不落在看起来奇不奇怪上。**

**归因**（`diagnose`）：只对已经检出的事务做，三类根因各有确定性判据：

  - `out_of_order`  ── 事件的到达顺序（seq）与业务时间（occurred_at）错位，
                       且 B 的终态正好等于「按到达顺序处理」的结果，
                       A 的终态正好等于「按业务时间处理」的结果。
                       **这一条只看两张表判不出来**，必须回到事件流。
  - `timezone`      ── 金额与状态完全相同，B 的时间戳恰好等于 A 的 UTC 瞬时值
                       （即 B 把 UTC 当本地时间入库），差值恰好是时区偏移。
  - `model_mismatch`── 时间与状态一致，两边金额之比恰好是 100 的整数次幂。

这三条都是可判定的，用规则比用模型更稳、更快、更便宜。模型的价值在诊断报告的
可读性和规则没覆盖到的长尾（见 `llm.py`），不在这里。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

# 系统 B 的 occurred_at 不带偏移，约定为北京时间（见 fixtures/generate.py 的建表注释）
LOCAL_TZ = timezone(timedelta(hours=8))

ROOT_CAUSES = ("timezone", "out_of_order", "model_mismatch")

FIELDS = ("status", "amount_cents", "book_date", "occurred_at")


# ── 时间处理 ───────────────────────────────────────────────────
def parse_ts(value: str) -> datetime:
    """解析 ISO8601。不带偏移的按本地时区（+08:00）理解——这是 B 的约定。"""
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=LOCAL_TZ) if dt.tzinfo is None else dt


def local_naive(value: str) -> str:
    """把任意 ISO8601 渲染成 B 那一列的格式：本地时间、不带偏移。"""
    return parse_ts(value).astimezone(LOCAL_TZ).replace(tzinfo=None).isoformat()


def tz_shift(a_ts: str, b_ts: str) -> timedelta | None:
    """B 是不是把 A 的 UTC 瞬时值当本地时间存了下来？是就返回偏移量。

    判据是「差值**恰好等于**时区偏移」，不是「差值不为零」。跨天、跨月本身
    都不是证据——N-3003 就发生在 23:58，两边一致，这里必须返回 None。
    """
    a = datetime.fromisoformat(a_ts)
    b = datetime.fromisoformat(b_ts)
    if a.tzinfo is None or b.tzinfo is not None:
        return None  # 只处理「A 带偏移、B 不带」这一种接入形态
    offset = a.utcoffset()
    if not offset:
        return None
    a_utc_naive = (a - offset).replace(tzinfo=None)
    a_local_naive = a.replace(tzinfo=None)
    if b == a_utc_naive and b != a_local_naive:
        return offset
    return None


# ── 金额处理 ───────────────────────────────────────────────────
def hundred_power(a_amount: int, b_amount: int) -> int | None:
    """B / A 是不是恰好 100 的整数次幂？是就返回幂次（正数表示 B 偏大）。

    「恰好」很重要：N-3004 是一亿分的大额，但两边一样大，比值是 1，
    幂次为 0，这里返回 None。**大额不是证据，比值才是。**
    """
    if a_amount == 0 or b_amount == 0 or (a_amount > 0) != (b_amount > 0):
        return None
    big, small, sign = abs(b_amount), abs(a_amount), 1
    if big < small:
        big, small, sign = small, big, -1
    if big % small:
        return None
    ratio, power = big // small, 0
    while ratio % 100 == 0:
        ratio //= 100
        power += 1
    return sign * power if ratio == 1 and power else None


# ── 检出 ───────────────────────────────────────────────────────
def diff_fields(a: dict, b: dict) -> list[str]:
    """两边终态有哪些字段对不上。时间按瞬时值比，不按字面量比。"""
    out = []
    if a["status"] != b["status"]:
        out.append("status")
    if a["amount_cents"] != b["amount_cents"]:
        out.append("amount_cents")
    if a["book_date"] != b["book_date"]:
        out.append("book_date")
    if parse_ts(a["occurred_at"]) != parse_ts(b["occurred_at"]):
        out.append("occurred_at")
    return out


def compare(a_rows: dict[str, dict], b_rows: dict[str, dict]) -> list[dict]:
    """全量对账，返回终态不一致的事务（按 txn_id 排序）。"""
    findings = []
    for txn_id in sorted(set(a_rows) | set(b_rows)):
        a, b = a_rows.get(txn_id), b_rows.get(txn_id)
        if a is None or b is None:
            findings.append({"txn_id": txn_id, "fields": ["missing"],
                             "a": a, "b": b})
            continue
        fields = diff_fields(a, b)
        if fields:
            findings.append({"txn_id": txn_id, "fields": fields, "a": a, "b": b})
    return findings


# ── 归因 ───────────────────────────────────────────────────────
def _arrival_vs_business(events: Iterable[dict]) -> tuple[dict, dict, bool] | None:
    """按到达顺序处理 vs 按业务时间处理，各自的终态事件；以及是否真的乱序。"""
    evs = [e for e in events if e.get("status")]
    if len(evs) < 2:
        return None
    by_seq = sorted(evs, key=lambda e: e["seq"])
    by_time = sorted(evs, key=lambda e: (parse_ts(e["occurred_at"]), e["seq"]))
    inverted = [e["seq"] for e in by_seq] != [e["seq"] for e in by_time]
    return by_seq[-1], by_time[-1], inverted


def diagnose(a: dict, b: dict, events: list[dict]) -> dict[str, Any]:
    """给一条已检出的不一致定根因。返回 root_cause / detail / evidence。"""
    ev = _arrival_vs_business(events)

    # ① 乱序到达：只看表判不出来，必须看事件流
    if ev:
        arrival, business, inverted = ev
        if (inverted and arrival["status"] != business["status"]
                and b["status"] == arrival["status"]
                and a["status"] == business["status"]):
            return {
                "root_cause": "out_of_order",
                "detail": (
                    f"事件到达顺序与业务时间错位："
                    f"{business['status']}(seq={business['seq']}, {business['occurred_at']}) "
                    f"业务上更晚，却先于 "
                    f"{arrival['status']}(seq={arrival['seq']}, {arrival['occurred_at']}) 到达；"
                    f"B 按到达顺序覆盖，终态回退为 {b['status']}，"
                    f"A 的终态是 {a['status']}，这笔在财务侧从未入账"
                ),
                "evidence": {
                    "arrival_final": arrival, "business_final": business,
                    "trace": [{"seq": e["seq"], "status": e["status"],
                               "occurred_at": e["occurred_at"]}
                              for e in sorted(events, key=lambda x: x["seq"])],
                },
            }

    # ② 时区换算：金额、状态全对，时间差恰好等于时区偏移
    shift = tz_shift(a["occurred_at"], b["occurred_at"])
    if (shift is not None and a["status"] == b["status"]
            and a["amount_cents"] == b["amount_cents"]):
        hours = shift.total_seconds() / 3600
        crossed = "，且跨月" if a["book_date"][:7] != b["book_date"][:7] else (
            "，且跨天" if a["book_date"] != b["book_date"] else "")
        return {
            "root_cause": "timezone",
            "detail": (
                f"金额（{a['amount_cents']} 分）与状态（{a['status']}）两边完全相同，"
                f"B 的 occurred_at={b['occurred_at']} 恰好是 A 的 UTC 瞬时值，"
                f"差值恰好等于时区偏移 {hours:+.0f}h——B 把 UTC 值当本地时间入库；"
                f"入账日因此 A 记 {a['book_date']}、B 记 {b['book_date']}{crossed}"
            ),
            "evidence": {"offset_hours": hours,
                         "a_occurred_at": a["occurred_at"],
                         "b_occurred_at": b["occurred_at"]},
        }

    # ③ 数据模型不对齐：时间状态一致，金额之比恰好是 100 的整数次幂
    power = hundred_power(a["amount_cents"], b["amount_cents"])
    if (power and a["status"] == b["status"]
            and parse_ts(a["occurred_at"]) == parse_ts(b["occurred_at"])):
        factor = 100 ** abs(power)
        side = "偏大" if power > 0 else "偏小"
        return {
            "root_cause": "model_mismatch",
            "detail": (
                f"时间与状态两边一致，金额之比恰好是 {factor}："
                f"A={a['amount_cents']} 分、B={b['amount_cents']} 分，B {side} {factor} 倍。"
                f"A 的单位是分，B 接入时把它当成元又写进了分字段"
            ),
            "evidence": {"factor": factor, "power": power,
                         "a_amount_cents": a["amount_cents"],
                         "b_amount_cents": b["amount_cents"]},
        }

    # 三条判据都不命中：宁可说不知道，也不要瞎猜一个根因塞进补偿 SQL
    return {
        "root_cause": "unknown",
        "detail": ("终态不一致但不匹配任何已知判据，需人工介入；"
                   f"差异字段：{'、'.join(diff_fields(a, b))}"),
        "evidence": {"a": a, "b": b},
    }


# ── 起草补偿（只生成文本，绝不执行） ──────────────────────────
def compensation_sql(txn_id: str, a: dict, b: dict, root_cause: str) -> list[str]:
    """按根因套模板生成补偿语句。三类方向不同，诊断错了这里就会错。

    统一以 A（订单系统）为准修 B（财务台账），且**只改需要改的列**：
    时区类不动金额，单位类不动时间。

    每条 WHERE 除了 txn_id 还带上「诊断时看到的 B 侧原值」。这一条不是为了好看：
    草案落盘到复核人点执行之间隔着人的时间，这期间 B 侧可能已经被别的流程改过；
    带原值的 WHERE 让这种情况下语句直接不匹配（改动 0 行），而不是把一份基于
    过期证据的结论盖上去。副作用是补偿脚本天然幂等——重复执行不会二次换算。
    """
    q = txn_id.replace("'", "''")
    if root_cause == "timezone":
        # 只修时间与入账日，金额一分不动
        return [f"UPDATE sys_b_txn SET occurred_at = '{local_naive(a['occurred_at'])}', "
                f"book_date = '{a['book_date']}' WHERE txn_id = '{q}' "
                f"AND occurred_at = '{b['occurred_at']}' AND book_date = '{b['book_date']}';"]
    if root_cause == "out_of_order":
        # 把被回退的终态推进到 A 的终态，并补回金额
        sets = [f"status = '{a['status']}'", f"amount_cents = {a['amount_cents']}"]
        if a["book_date"] != b["book_date"]:
            sets.append(f"book_date = '{a['book_date']}'")
        return [f"UPDATE sys_b_txn SET {', '.join(sets)} WHERE txn_id = '{q}' "
                f"AND status = '{b['status']}' AND amount_cents = {b['amount_cents']};"]
    if root_cause == "model_mismatch":
        power = hundred_power(a["amount_cents"], b["amount_cents"]) or 0
        factor = 100 ** abs(power)
        op = "/" if power > 0 else "*"
        # 用比例换算而不是直接写死目标值：写死等于把 A 的数抄过去，
        # 掩盖了「单位错了」这件事，也无法推广到同一批次的其它记录
        return [f"UPDATE sys_b_txn SET amount_cents = CAST(amount_cents {op} {factor} AS INTEGER) "
                f"WHERE txn_id = '{q}' AND amount_cents = {b['amount_cents']};"]
    return [f"-- {txn_id}: 根因未定（{root_cause}），不生成补偿语句，需人工判断"]
