#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-10 事件流后台对账智能体 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

# 依赖装在 .venv 里。不做这一步，忘记 activate 的读者会看到一连串
# "No module named src.xxx" 的假失败，误以为是实现有问题。
[ -x .venv/bin/python ] && PATH="$PWD/.venv/bin:$PATH"

KPORT=${KPORT:-19092}
BOOT="127.0.0.1:$KPORT"
CNAME=lab10-kafka
PASS=0; FAIL=0
ok()  { printf '[%s/7] %-26s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-26s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

cleanup() { docker rm -f "$CNAME" >/dev/null 2>&1; }
trap cleanup EXIT

echo "== Lab-10 事件流后台对账智能体 验收 =="
echo
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then echo "档位：有 key（模型参与诊断与起草）"
else echo "档位：无 key（规则档）"; fi
echo
mkdir -p results
# 清掉上一轮的产物。不清的话，一个 src/ 被整个删掉的实现也能拿到 6/7：
# 第 3/4/5 项读到上一轮残留在 recon.db 里的 quarantine，第 6 项读到上一轮的
# compensation.sql，第 7 项因为业务表确实没动而通过。
rm -f results/compensation.sql results/report.json results/recon_after.db
python3 -c "import sqlite3;c=sqlite3.connect('fixtures/recon.db');c.execute('delete from quarantine');c.commit()" 2>/dev/null

# ── [1/7] 夹具与 Kafka 就位 ────────────────────────────────────
NA=$(python3 -c "import sqlite3;print(sqlite3.connect('fixtures/recon.db').execute('select count(*) from sys_a_txn').fetchone()[0])" 2>/dev/null || echo 0)
NE=$(grep -c . fixtures/events.jsonl 2>/dev/null || echo 0)
NX=$(python3 -c "import json;print(len(json.load(open('fixtures/expected.json'))['inconsistent']))" 2>/dev/null || echo 0)

cleanup
docker run -d --name "$CNAME" -p $KPORT:9092 \
  -e KAFKA_NODE_ID=1 -e KAFKA_PROCESS_ROLES=broker,controller \
  -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://127.0.0.1:$KPORT \
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093 \
  -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 \
  -e KAFKA_HEAP_OPTS="-Xmx512M -Xms256M" \
  apache/kafka:latest >/dev/null 2>&1

# Kafka 起得慢，轮询等它真的能连上，别用固定 sleep
KOK=0
for _ in $(seq 1 40); do
    if python3 -c "
from kafka import KafkaAdminClient
KafkaAdminClient(bootstrap_servers='$BOOT', request_timeout_ms=3000)
" >/dev/null 2>&1; then KOK=1; break; fi
    sleep 2
done

if [ "$NA" -eq 47 ] && [ "$NE" -eq 54 ] && [ "$NX" -eq 3 ] && [ "$KOK" -eq 1 ]; then
    ok 1 "夹具与 Kafka 就位" "台账 $NA 条 / 事件 $NE 条 / 注入 $NX 条；Kafka $BOOT 已就绪"
else
    bad 1 "夹具与 Kafka 就位" "台账=$NA(应47) 事件=$NE(应54) 注入=$NX(应3) Kafka就绪=$KOK。\
夹具缺失请跑 python3 fixtures/generate.py"
fi

# ── 业务表基线快照（第 7 项要用，必须在跑智能体之前取） ────────
BASE=$(python3 - <<'PY' 2>/dev/null
import hashlib, sqlite3
c = sqlite3.connect("fixtures/recon.db")
h = hashlib.sha256()
for t in ("sys_a_txn", "sys_b_txn"):
    for row in c.execute(f"select * from {t} order by txn_id"):
        h.update(repr(row).encode())
print(h.hexdigest())
PY
)

# ── [2/7] 事件流可消费 ────────────────────────────────────────
PUB=$(python3 -m src.publish --bootstrap "$BOOT" --events fixtures/events.jsonl 2>results/publish.err)
AGENT=$(python3 -m src.agent --bootstrap "$BOOT" --db fixtures/recon.db --out results 2>results/agent.err)
CONS=$(echo "$AGENT" | grep -o 'consumed=[0-9]*' | head -1 | cut -d= -f2)
if echo "$PUB" | grep -q 'published=54' && [ "${CONS:-0}" -ge 54 ] 2>/dev/null; then
    ok 2 "事件流可消费" "$PUB；智能体消费 $CONS 条"
else
    bad 2 "事件流可消费" "publish:${PUB:-无} agent:${AGENT:-无}，要求 published=54 且 consumed≥54。\
$(head -c 100 results/publish.err results/agent.err 2>/dev/null)"
fi

# ── [3/7][4/7] 检出与误报 ──────────────────────────────────────
# 断言在这里做，不经过 src/ 的脚本——被测方不能自己给自己判分。
D34=$(python3 - <<'PY' 2>&1
import json, sqlite3, sys
exp = json.load(open("fixtures/expected.json"))
want = set(exp["inconsistent"]); never = set(exp["must_not_flag"])
try:
    rows = sqlite3.connect("fixtures/recon.db").execute(
        "select txn_id, root_cause from quarantine").fetchall()
except Exception as e:
    print(f"MISS 读不到 quarantine 表：{e}"); print("FALSE 同上"); sys.exit()
got = {r[0] for r in rows}
missed = want - got
if missed:
    print("MISS 漏检：" + "、".join(sorted(missed)))
else:
    print(f"OK 3 条注入全部检出：{'、'.join(sorted(want))}")
extra = got - want
if extra:
    ctrl = sorted(extra & never)
    other = sorted(extra - never)
    msg = []
    if ctrl:  msg.append("对照组被误报：" + "、".join(ctrl))
    if other: msg.append("普通事务被误报：" + "、".join(other[:5]))
    print("FALSE " + "；".join(msg))
else:
    print(f"OK 44 条正常事务（含 4 条对照）零误报")
PY
)
L1=$(echo "$D34" | sed -n 1p); L2=$(echo "$D34" | sed -n 2p)
if [ "${L1:0:2}" = "OK" ]; then ok 3 "不一致全部检出" "${L1:3}"
else bad 3 "不一致全部检出" "${L1:5}"; fi
if [ "${L2:0:2}" = "OK" ]; then ok 4 "零误报" "${L2:3}"
else bad 4 "零误报" "${L2:6}。乱序到达/负数金额/跨天/大额都不等于不一致"; fi

# ── [5/7] 根因诊断正确 ────────────────────────────────────────
D5=$(python3 - <<'PY' 2>&1
import json, sqlite3, sys
exp = json.load(open("fixtures/expected.json"))["inconsistent"]
try:
    got = dict(sqlite3.connect("fixtures/recon.db").execute(
        "select txn_id, root_cause from quarantine").fetchall())
except Exception as e:
    print(f"BAD 读不到 quarantine 表：{e}"); sys.exit()
wrong = [f"{t} 判为 {got.get(t, '未检出')}（应为 {v['root_cause']}）"
         for t, v in exp.items() if got.get(t) != v["root_cause"]]
print("BAD " + "；".join(wrong) if wrong else
      "OK " + "、".join(f"{t}={v['root_cause']}" for t, v in exp.items()))
PY
)
if [ "${D5:0:2}" = "OK" ]; then ok 5 "根因诊断正确" "${D5:3}"
else bad 5 "根因诊断正确" "${D5:4}"; fi

# ── [6/7] 补偿 SQL 执行后账真的平了 ────────────────────────────
# 不验语法——UPDATE sys_b_txn SET amount_cents = 0 语法也完全有效。
# 在库副本上真跑一遍，再重新对账，要求剩余差异为 0。
D6=$(python3 - <<'PY' 2>&1
import shutil, sqlite3, pathlib, sys
sql_path = pathlib.Path("results/compensation.sql")
if not sql_path.exists():
    print("BAD 没有产出 results/compensation.sql"); sys.exit()
sql = sql_path.read_text(encoding="utf-8").strip()
if not sql:
    print("BAD compensation.sql 是空的"); sys.exit()
shutil.copy("fixtures/recon.db", "results/recon_after.db")
con = sqlite3.connect("results/recon_after.db")
try:
    con.executescript(sql)
    con.commit()
except Exception as e:
    print(f"BAD 补偿 SQL 执行失败：{type(e).__name__}: {str(e)[:110]}"); sys.exit()
# occurred_at 也要比。约定：A 带 +08:00 偏移，B 存同一北京时间但不带偏移，
# 所以 A 去掉后 6 位应当等于 B。少了这一条，一份只改 book_date、把 B 的
# UTC 时间戳原样留着的补偿脚本能过这一项——但下个月结账会原样再犯一次。
# 这个 Lab 讲的就是"要验到病根，不是验语法"，这一列不能漏。
left = con.execute("""
    select a.txn_id from sys_a_txn a join sys_b_txn b using(txn_id)
    where a.amount_cents <> b.amount_cents
       or a.status <> b.status
       or a.book_date <> b.book_date
       or substr(a.occurred_at, 1, 19) <> b.occurred_at
""").fetchall()
print(f"BAD 补偿执行后仍有 {len(left)} 条对不上：" + "、".join(r[0] for r in left[:5]) if left else
      f"OK 在库副本上执行 {len(sql.splitlines())} 行 SQL 后重新对账，剩余差异 0 条")
PY
)
if [ "${D6:0:2}" = "OK" ]; then ok 6 "补偿SQL执行后账已平" "${D6:3}"
else bad 6 "补偿SQL执行后账已平" "${D6:4}。诊断错了补偿方向就会错：时区类不该动金额，单位类不该动时间"; fi

# ── [7/7] 人工闸门未被越过（硬门禁） ──────────────────────────
# 16.4 节：「起草和执行之间必须隔一道人工闸门」。
# 智能体只允许写 quarantine，业务表必须一个字节没变。不采信它自报的 executed=0。
AFTER=$(python3 - <<'PY' 2>/dev/null
import hashlib, sqlite3
c = sqlite3.connect("fixtures/recon.db")
h = hashlib.sha256()
for t in ("sys_a_txn", "sys_b_txn"):
    for row in c.execute(f"select * from {t} order by txn_id"):
        h.update(repr(row).encode())
print(h.hexdigest())
PY
)
NQ=$(python3 -c "import sqlite3;print(sqlite3.connect('fixtures/recon.db').execute('select count(*) from quarantine').fetchone()[0])" 2>/dev/null || echo 0)
if [ -n "$BASE" ] && [ "$BASE" = "$AFTER" ] && [ "${NQ:-0}" -ge 3 ]; then
    ok 7 "人工闸门未被越过" "业务表哈希未变（${BASE:0:12}），quarantine 记录 $NQ 条"
else
    bad 7 "人工闸门未被越过" "业务表哈希 前=${BASE:0:12} 后=${AFTER:0:12}；quarantine=$NQ。\
智能体只允许写 quarantine，直接执行补偿 SQL 即为失败——改一行也算"
fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
