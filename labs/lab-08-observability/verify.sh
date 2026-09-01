#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-08 可观测性、日志脱敏与成本看板 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

# 依赖装在 .venv 里。不做这一步，忘记 activate 的读者会看到一连串
# "No module named src.xxx" 的假失败，误以为是实现有问题。
[ -x .venv/bin/python ] && PATH="$PWD/.venv/bin:$PATH"

PORT=${PORT:-13000}
INGEST="http://127.0.0.1:$PORT"
PASS=0; FAIL=0
ok()  { printf '[%s/7] %-26s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-26s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

cleanup() { pkill -f 'fixtures/mock_langfuse.py' 2>/dev/null; sleep 0.3; }
trap cleanup EXIT
cleanup

echo "== Lab-08 可观测性、日志脱敏与成本看板 验收 =="
echo
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    echo "档位：有 key（deepseek-chat，真实 token 与成本）"
else
    echo "档位：无 key（本地 Ollama，token 为真、API 成本为 0）"
fi
echo
mkdir -p results

# ── [1/7] 夹具与 SDK 就位 ──────────────────────────────────────
NC=$(grep -c . fixtures/pii_cases.jsonl 2>/dev/null || echo 0)
LV=$(python3 -c "import importlib.metadata as m;print(m.version('langfuse'))" 2>/dev/null || echo "")
HASP=$(python3 -c "import json;d=json.load(open('fixtures/pricing.json'));print(len(d['models']))" 2>/dev/null || echo 0)
if [ "$NC" -eq 8 ] && [ -n "$LV" ] && [ "$HASP" -ge 2 ]; then
    ok 1 "夹具与 SDK 就位" "8 条用例；langfuse $LV；单价表 $HASP 个模型"
else
    bad 1 "夹具与 SDK 就位" "用例=$NC(应8) langfuse='${LV:-未安装}' 单价表模型数=$HASP(应≥2)"
fi

# ── [2/7] mock 摄取端可用 ──────────────────────────────────────
python3 fixtures/mock_langfuse.py --port "$PORT" > results/ingest.log 2>&1 &
sleep 1.5
UP=$(curl -s --max-time 5 "$INGEST/_health" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("ok",False))' 2>/dev/null || echo False)
if [ "$UP" = "True" ]; then
    ok 2 "mock 摄取端可用" "监听 $INGEST"
else
    bad 2 "mock 摄取端可用" "健康检查失败，见 results/ingest.log"
fi

# ── 跑一遍被观测的流水线 ───────────────────────────────────────
curl -s --max-time 5 -X POST "$INGEST/_reset" > /dev/null
RUN=$(python3 -m src.app --ingest "$INGEST" --cases fixtures/pii_cases.jsonl 2>results/app.err)
sleep 2   # 留出 flush 时间

# ── [3/7] trace 结构完整 ───────────────────────────────────────
D3=$(python3 - "$INGEST" <<'PY' 2>&1
import json, sys, urllib.request
spans = json.load(urllib.request.urlopen(sys.argv[1] + "/_spans", timeout=10))
if not spans:
    print("BAD 没有收到任何 span"); sys.exit()
by_trace = {}
for s in spans:
    by_trace.setdefault(s["trace_id"], []).append(s)
probs, gens = [], 0
for tid, ss in by_trace.items():
    roots = [s for s in ss if not s["parent_span_id"]]
    if len(roots) != 1:
        probs.append(f"trace {tid[:8]} 有 {len(roots)} 个根 span（应为 1）")
    if len(ss) < 2:
        probs.append(f"trace {tid[:8]} 只有 {len(ss)} 个 span，没有体现步骤拆分")
for s in spans:
    if str(s["attributes"].get("langfuse.observation.type", "")).lower() == "generation":
        gens += 1
if gens == 0:
    probs.append("没有任何 span 被标为 generation 类型")
print("BAD " + "；".join(probs[:3]) if probs else
      f"OK {len(by_trace)} 条 trace / {len(spans)} 个 span，各有唯一根 span，generation 类 {gens} 个")
PY
)
if [ "${D3:0:2}" = "OK" ]; then ok 3 "trace 结构完整" "${D3:3}"
else bad 3 "trace 结构完整" "${D3:4}｜app 输出:${RUN:-无} $(head -c 60 results/app.err 2>/dev/null)"; fi

# ── [4/7] PII 零泄漏（硬门禁） ─────────────────────────────────
# 在原始上报字节上搜，不在解码后的字段上搜——后者验不住把 PII
# 塞进未解析字段/异常堆栈/span 名字的实现。一次出现即失败，不设比例。
D4=$(python3 - "$INGEST" <<'PY' 2>&1
import json, sys, urllib.request
raw = json.load(urllib.request.urlopen(sys.argv[1] + "/_raw", timeout=10))
blob = bytes.fromhex(raw["hex"])
if raw["payloads"] == 0:
    print("BAD 摄取端没收到任何上报负载"); sys.exit()
leaks = []
for line in open("fixtures/pii_cases.jsonl", encoding="utf-8"):
    c = json.loads(line)
    for v in c["must_mask"]:
        # 必须同时搜两种形态。Langfuse SDK 对 dict/list 形态的 input/output
        # 用 json.dumps(ensure_ascii=True) 序列化，中文会变成 \uXXXX 转义，
        # 只搜原样 UTF-8 的话，一个把 input 包成 [{"role":..,"content":..}]
        # 且完全不做姓名/地址脱敏的实现会直接蒙混过关——而那恰好是本 Lab 最难的一半。
        esc = json.dumps(v, ensure_ascii=True)[1:-1].encode("utf-8")
        if v.encode("utf-8") in blob or esc in blob:
            leaks.append(f"{c['id']}:{v}")
print("BAD 敏感串出现在原始上报字节里：" + "、".join(leaks[:4]) +
      (f"（共 {len(leaks)} 处）" if len(leaks) > 4 else "") if leaks else
      f"OK 检查了 {raw['payloads']} 个上报负载（{len(blob)} 字节），无敏感串泄漏")
PY
)
if [ "${D4:0:2}" = "OK" ]; then ok 4 "PII 零泄漏" "${D4:3}"
else bad 4 "PII 零泄漏" "${D4:4}。脱敏必须在上报之前，且要覆盖 input/output/异常信息所有路径"; fi

# ── [5/7] 脱敏不过度 ───────────────────────────────────────────
# 只有第 4 项的话，把整段文本全掩掉就能通过。这一项是它的对偶。
D5=$(python3 - "$INGEST" <<'PY' 2>&1
import json, sys, urllib.request
spans = json.load(urllib.request.urlopen(sys.argv[1] + "/_spans", timeout=10))
if not spans:
    # 没收到 span 时不能报「业务字段被掩掉了」——那是把「没跑起来」
    # 误诊成「脱敏过度」，会把人引向完全错误的方向。
    print("BAD 没有收到任何 span，本项无从判断；先看第 3 项"); sys.exit()
text = json.dumps(spans, ensure_ascii=False)
missing = []
for line in open("fixtures/pii_cases.jsonl", encoding="utf-8"):
    c = json.loads(line)
    for v in c["must_keep"]:
        if v not in text:
            missing.append(f"{c['id']}:{v}")
print("BAD 业务字段被掩掉了：" + "、".join(missing[:4]) +
      (f"（共 {len(missing)} 处）" if len(missing) > 4 else "") if missing else
      "OK 全部业务字段（单据号/工单号/金额/日期）在 span 里仍可见")
PY
)
if [ "${D5:0:2}" = "OK" ]; then ok 5 "脱敏不过度" "${D5:3}"
else bad 5 "脱敏不过度" "${D5:4}。正则太宽：\\d{11} 会吃掉任意 11 位数字，\\d{6,} 会吃掉金额"; fi

# ── [6/7] 每次调用成本可见且算得对 ─────────────────────────────
COST=$(python3 -m src.cost --ingest "$INGEST" --pricing fixtures/pricing.json --out results 2>results/cost.err)
D6=$(python3 - <<'PY' 2>&1
import json, sys
try:
    r = json.load(open("results/cost_report.json"))
except Exception as e:
    print(f"BAD 读不到 results/cost_report.json（{e}）"); sys.exit()
pr = json.load(open("fixtures/pricing.json"))
per = pr["_per_tokens"]
calls = r.get("calls") or []
if not calls:
    print("BAD cost_report.json 里没有 calls"); sys.exit()
probs = []
for c in calls[:50]:
    for k in ("model", "input_tokens", "output_tokens", "cost_cny"):
        if k not in c:
            probs.append(f"调用记录缺字段 {k}"); break
    else:
        m = pr["models"].get(c["model"])
        if not m:
            probs.append(f"单价表里没有模型 {c['model']}"); continue
        # 按单价表独立重算，不采信实现自报的数字
        want = c["input_tokens"] * m["input"] / per + c["output_tokens"] * m["output"] / per
        if abs(want - c["cost_cny"]) > max(1e-9, want * 1e-6):
            probs.append(f"{c['model']} 成本对不上：报 {c['cost_cny']:.8f} 重算 {want:.8f}")
    if probs:
        break
tot_in = sum(c.get("input_tokens", 0) for c in calls)
tot_out = sum(c.get("output_tokens", 0) for c in calls)
if not probs and (tot_in <= 0 or tot_out <= 0):
    # 全部调用失败时 token 全 0、成本全 0，"重算一致"照样成立。
    # key 过期 / Ollama 没起 / 网络不通会以"验收通过"的形态呈现，
    # 无 key 档尤其隐蔽——本地单价本来就是 0。
    probs.append(f"token 总数为 0（in={tot_in} out={tot_out}），说明模型调用全部失败，不是真的跑通了")
print("BAD " + probs[0] if probs else
      f"OK {len(calls)} 次调用均带 token 数与成本（in={tot_in} out={tot_out}），按单价表独立重算一致")
PY
)
if [ "${D6:0:2}" = "OK" ]; then ok 6 "调用成本可见且算得对" "${D6:3}"
else bad 6 "调用成本可见且算得对" "${D6:4}｜cost 输出:${COST:-无} $(head -c 60 results/cost.err 2>/dev/null)"; fi

# ── [7/7] 成本看板按业务动作聚合 ───────────────────────────────
D7=$(python3 - <<'PY' 2>&1
import json, sys
try:
    r = json.load(open("results/cost_report.json"))
except Exception:
    print("BAD 无 cost_report.json，见第 6 项"); sys.exit()
by = r.get("by_action") or {}
if not by:
    print("BAD cost_report.json 缺 by_action"); sys.exit()
probs = []
for name, v in by.items():
    for k in ("calls", "total_cny", "avg_cny"):
        if k not in v:
            probs.append(f"动作 {name} 缺字段 {k}")
    if not probs and v["calls"] > 0 and abs(v["total_cny"] / v["calls"] - v["avg_cny"]) > 1e-9:
        probs.append(f"动作 {name} 的均价与总额/次数对不上")
print("BAD " + probs[0] if probs else
      f"OK 按业务动作聚合 {len(by)} 项：" +
      "、".join(f"{k}({v['calls']}次 均 {v['avg_cny']:.6f}元)" for k, v in list(by.items())[:3]))
PY
)
if [ "${D7:0:2}" = "OK" ]; then ok 7 "成本看板按动作聚合" "${D7:3}"
else bad 7 "成本看板按动作聚合" "${D7:4}"; fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
