#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-03 遗留 API 封装为 MCP Server · 验收脚本
#
# 8 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

# 本 Lab 的依赖装在 .venv 里。不做这一步的话，忘记 activate 的读者会看到
# 一连串 "No module named src.xxx" 的假失败，误以为是实现有问题。
[ -x .venv/bin/python ] && PATH="$PWD/.venv/bin:$PATH"

C=fixtures/certs
ERP_PORT=19543
ERP="https://127.0.0.1:$ERP_PORT"
PASS=0; FAIL=0
ok()  { printf '[%s/8] %-26s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/8] %-26s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

cleanup() { pkill -f 'fixtures/mock_erp.py' 2>/dev/null; sleep 0.3; }
trap cleanup EXIT
cleanup

echo "== Lab-03 遗留 API 封装为 MCP Server 验收 =="
echo

if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    TIER="API（deepseek-chat，真实模型选工具）"
else
    TIER="无 key 降级（静态描述质量检查）"
fi
echo "第 8 项档位：$TIER"
echo

mkdir -p results
FAULT_CURL=(curl -s --max-time 10 --cacert "$C/ca.crt" --cert "$C/bridge-client.crt" --key "$C/bridge-client.key")

# ── [1/8] 夹具与证书完整 ───────────────────────────────────────
MISS=""
for f in ca.crt erp-server.crt erp-server.key bridge-client.crt bridge-client.key; do
    [ -f "$C/$f" ] || MISS="$MISS $f"
done
N_SEL=$(grep -c . fixtures/tool_selection.jsonl 2>/dev/null || echo 0)
if [ -z "$MISS" ] && [ "$N_SEL" -eq 10 ]; then
    ok 1 "夹具与证书完整" "5 个证书文件齐；测试集 10 条"
else
    bad 1 "夹具与证书完整" "缺证书:${MISS:-无}；测试集 $N_SEL 条（应为 10）。先跑 bash fixtures/gen_certs.sh"
fi

# ── 拉起 mock ERP ──────────────────────────────────────────────
python3 fixtures/mock_erp.py --port $ERP_PORT > results/erp.log 2>&1 &
sleep 2.0
ERP_UP=$("${FAULT_CURL[@]}" -o /dev/null -w '%{http_code}' "$ERP/erp/v2/_stats" || echo 000)
if [ "$ERP_UP" != "200" ]; then
    echo "!! mock ERP 未就绪（HTTP $ERP_UP），后续检查结果不可信。见 results/erp.log"
fi

# ── [2/8] 工具可发现且描述合格 ─────────────────────────────────
# 断言直接在这里做，不经过 src/ 里的检查脚本——被测方不能自己给自己判分。
python3 -m src.check_tools --mode dump --erp "$ERP" > results/tools.json 2>results/dump.err
D2=$(python3 - <<'PY' 2>&1
import json, sys
try:
    tools = json.load(open("results/tools.json"))
except Exception as e:
    print(f"BAD 无法解析 dump 输出: {e}"); sys.exit()
want = {"get_order_status", "add_order_note", "approve_order"}
got = {t["name"] for t in tools}
if got != want:
    print(f"BAD 工具名不符，期望 {sorted(want)} 实得 {sorted(got)}"); sys.exit()
probs = []
for t in tools:
    d, n = t.get("description") or "", t["name"]
    if len(d) < 150:
        probs.append(f"{n} 描述仅 {len(d)} 字，过短")
    if not any(k in d for k in ("适用", "什么时候", "何时")):
        probs.append(f"{n} 未说明适用场景")
    if not any(k in d for k in ("不适用", "不要", "请改用", "不应")):
        probs.append(f"{n} 未说明边界/不适用场景")
    if "ORD-" not in d:
        probs.append(f"{n} 未给出订单号格式示例")
    if not any(k in d for k in ("返回", "Returns")):
        probs.append(f"{n} 未说明返回结构")
    if n == "approve_order" and not any(k in d for k in ("不可逆", "不可撤销")):
        probs.append("approve_order 未标明不可逆")
print("BAD " + "；".join(probs[:3]) if probs else f"OK 3 个工具，描述最短 {min(len(t.get('description') or '') for t in tools)} 字")
PY
)
if [ "${D2:0:2}" = "OK" ]; then ok 2 "工具可发现且描述合格" "${D2:3}"
else bad 2 "工具可发现且描述合格" "${D2:4}$(head -c 80 results/dump.err 2>/dev/null)"; fi

# ── [3/8] 三个工具端到端穿透 mTLS ──────────────────────────────
INV=$(python3 -m src.check_tools --mode invoke --erp "$ERP" 2>results/invoke.err)
if echo "$INV" | grep -q 'query=OK' && echo "$INV" | grep -q 'note=OK' \
   && echo "$INV" | grep -q 'approve=OK' && echo "$INV" | grep -q 'cn=mcp-bridge-01'; then
    ok 3 "三工具端到端穿透" "$INV"
else
    bad 3 "三工具端到端穿透" "${INV:-无输出}$(head -c 80 results/invoke.err 2>/dev/null)"
fi

# ── [4/8] 凭据不泄漏到模型侧 ───────────────────────────────────
D4=$(python3 - <<'PY' 2>&1
import json, re, sys
try:
    tools = json.load(open("results/tools.json"))
except Exception:
    print("BAD 无 dump 输出，见第 2 项"); sys.exit()
cred = re.compile(r"token|cert|secret|password|credential|passwd|\bkey\b", re.I)
path = re.compile(r"\.pem|\.crt|\.key|certs/|private", re.I)
bad = []
for t in tools:
    for p in (t.get("input_schema") or {}).get("properties", {}):
        if cred.search(p):
            bad.append(f"{t['name']} 入参 {p} 像凭据")
    if path.search(t.get("description") or ""):
        bad.append(f"{t['name']} 描述里出现证书路径")
print("BAD " + "；".join(bad[:3]) if bad else
      f"OK 入参共 {sum(len((t.get('input_schema') or {}).get('properties',{})) for t in tools)} 个，无凭据字段")
PY
)
if [ "${D4:0:2}" = "OK" ]; then ok 4 "凭据不泄漏到模型侧" "${D4:3}"
else bad 4 "凭据不泄漏到模型侧" "${D4:4}"; fi

# ── [5/8] 重试生效 ─────────────────────────────────────────────
# 注入 2 次 503。工具应重试并最终成功，且 ERP 侧确实被打了 ≥3 次。
"${FAULT_CURL[@]}" -X POST "$ERP/erp/v2/_fault" \
    -d '{"mode":"flaky","count":2,"reset_stats":true}' > /dev/null
RET=$(python3 -m src.check_tools --mode retry --erp "$ERP" 2>results/retry.err)
ATT=$(echo "$RET" | grep -o 'erp_attempts=[0-9]*' | cut -d= -f2)
if echo "$RET" | grep -q 'result=ok' && [ "${ATT:-0}" -ge 3 ] 2>/dev/null; then
    ok 5 "重试生效" "$RET"
else
    bad 5 "重试生效" "${RET:-无输出}，要求 result=ok 且 erp_attempts≥3（注入了 2 次 503）"
fi
"${FAULT_CURL[@]}" -X POST "$ERP/erp/v2/_fault" -d '{"mode":"off"}' > /dev/null

# ── [6/8] 超时降级 ─────────────────────────────────────────────
# ERP 睡 5 秒。工具必须在预算内返回结构化错误，而不是把 5 秒原样传导给模型。
"${FAULT_CURL[@]}" -X POST "$ERP/erp/v2/_fault" \
    -d '{"mode":"timeout","sleep":5,"reset_stats":true}' > /dev/null
T0=$(date +%s%N)
DEG=$(python3 -m src.check_tools --mode degrade --erp "$ERP" 2>results/degrade.err)
T1=$(date +%s%N); DMS=$(( (T1 - T0) / 1000000 ))
# 必须确认 ERP 真的被调过——否则"工具压根没发请求"会被误判成"超时降级生效"。
DEG_HIT=$("${FAULT_CURL[@]}" "$ERP/erp/v2/_stats" \
          | python3 -c 'import sys,json;print(json.load(sys.stdin).get("total",0))' 2>/dev/null || echo 0)
if echo "$DEG" | grep -q 'retryable=true' && echo "$DEG" | grep -q 'raised=no' \
   && echo "$DEG" | grep -qi 'error=upstream_timeout' && [ "$DMS" -lt 4500 ] \
   && [ "${DEG_HIT:-0}" -ge 1 ] 2>/dev/null; then
    ok 6 "超时降级" "${DMS}ms 返回结构化错误（ERP 实收 ${DEG_HIT} 次）：$DEG"
else
    bad 6 "超时降级" "耗时 ${DMS}ms（须 <4500）ERP 实收 ${DEG_HIT} 次（须 ≥1）输出:${DEG:-无}。\
要求 error=upstream_timeout retryable=true raised=no；ERP 收到 0 次说明工具根本没发请求，不算降级"
fi
"${FAULT_CURL[@]}" -X POST "$ERP/erp/v2/_fault" -d '{"mode":"off"}' > /dev/null

# ── [7/8] 熔断生效 ─────────────────────────────────────────────
# 熔断的意义是不再打下游。只记状态却继续发请求，不算熔断。
"${FAULT_CURL[@]}" -X POST "$ERP/erp/v2/_fault" \
    -d '{"mode":"flaky","count":99,"reset_stats":true}' > /dev/null
# 探针报告熔断时 ERP 的累计调用数，然后再打 5 次。
# 「熔断后没再打 ERP」这件事由本脚本独立向 ERP 取数核对，不采信探针自报。
BRK=$(python3 -m src.check_tools --mode breaker --erp "$ERP" 2>results/breaker.err)
AT_TRIP=$(echo "$BRK" | grep -o 'erp_total_at_trip=[0-9]*' | cut -d= -f2)
POST=$(echo "$BRK" | grep -o 'post_trip_calls=[0-9]*' | cut -d= -f2)
FFMS=$(echo "$BRK" | grep -o 'fast_fail_ms=[0-9]*' | cut -d= -f2)
FINAL=$("${FAULT_CURL[@]}" "$ERP/erp/v2/_stats" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("total",0))' 2>/dev/null || echo -1)
if echo "$BRK" | grep -q 'tripped=yes' && [ "${POST:-0}" -ge 5 ] 2>/dev/null \
   && [ -n "${AT_TRIP:-}" ] && [ "${FINAL:--1}" -eq "${AT_TRIP:--2}" ] 2>/dev/null \
   && [ "${FFMS:-9999}" -lt 200 ] 2>/dev/null; then
    ok 7 "熔断生效" "$BRK；熔断后又打 ${POST} 次，ERP 累计仍为 ${FINAL}（独立核对）"
else
    bad 7 "熔断生效" "${BRK:-无输出}；熔断时 ERP 累计=${AT_TRIP:-?}，5 次后实测=${FINAL}。\
要求 tripped=yes、post_trip_calls≥5、fast_fail_ms<200，且熔断后 ERP 累计数不再增长"
fi
"${FAULT_CURL[@]}" -X POST "$ERP/erp/v2/_fault" -d '{"mode":"off"}' > /dev/null

# ── [8/8] 工具选择准确率 ───────────────────────────────────────
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    SEL=$(python3 -m src.tool_select --erp "$ERP" --cases fixtures/tool_selection.jsonl 2>results/select.err)
    CORR=$(echo "$SEL" | grep -o 'correct=[0-9]*' | cut -d= -f2)
    VIOL=$(echo "$SEL" | grep -o 'danger_violations=[0-9]*' | cut -d= -f2)
    if [ "${CORR:-0}" -ge 8 ] 2>/dev/null && [ "${VIOL:-99}" -eq 0 ] 2>/dev/null; then
        ok 8 "工具选择准确率" "$SEL（门槛 ≥8/10 且危险项零误触发）"
    else
        bad 8 "工具选择准确率" "${SEL:-无输出}$(head -c 80 results/select.err 2>/dev/null)。要求 correct≥8 且 danger_violations=0"
    fi
else
    # 无 key 档：静态描述质量，比第 2 项更严
    D8=$(python3 - <<'PY' 2>&1
import json, sys
try:
    tools = {t["name"]: (t.get("description") or "") for t in json.load(open("results/tools.json"))}
except Exception:
    print("BAD 无 dump 输出，见第 2 项"); sys.exit()
probs = []
ap = tools.get("approve_order", "")
if not any(k in ap for k in ("明确", "授权")):
    probs.append("approve_order 未要求「明确授权」才可调用")
if not any(k in ap for k in ("处理一下", "模糊", "含糊", "不构成")):
    probs.append("approve_order 未给出模糊表述的反面例子")
for n, d in tools.items():
    if not any(k in d for k in ("重试", "retry")):
        probs.append(f"{n} 未说明出错时是否该重试")
    if d.count("\n") < 3:
        probs.append(f"{n} 描述未分段，可读性差")
print("BAD " + "；".join(probs[:3]) if probs else
      f"OK 静态档通过：3 个工具描述均含授权边界、重试指引与反面例子")
PY
)
    if [ "${D8:0:2}" = "OK" ]; then ok 8 "描述质量（静态档）" "${D8:3}"
    else bad 8 "描述质量（静态档）" "${D8:4}"; fi
fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 8。
if [ $FAIL -eq 0 ] && [ $PASS -eq 8 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/8，失败 $FAIL。少于 8 项说明有检查未执行完。"; exit 1; fi
