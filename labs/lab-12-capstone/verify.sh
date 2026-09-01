#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-12 毕业项目 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] && PATH="$PWD/.venv/bin:$PATH"

PASS=0; FAIL=0
ok()  { printf '[%s/7] %-28s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-28s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

echo "== Lab-12 毕业项目 验收 =="
echo
mkdir -p results; rm -f results/*.json results/pipeline.log

# ── [1/7] 夹具就位 ─────────────────────────────────────────────
NC=$(python3 -c "
import json;d=json.load(open('fixtures/exit_criteria.json'))
print(sum(len(p['criteria']) for p in d['phases']))" 2>/dev/null || echo 0)
NP=$(python3 -c "import json;print(len(json.load(open('fixtures/exit_criteria.json'))['phases']))" 2>/dev/null || echo 0)
if [ "$NC" -eq 15 ] && [ "$NP" -eq 6 ] && [ -f fixtures/bad_submission/self_assessment.md ] \
   && [ -f fixtures/scenario/constraints.md ]; then
    ok 1 "夹具就位" "6 阶段 / $NC 条退出标准；场景包与负例提交齐备"
else
    bad 1 "夹具就位" "阶段=$NP(应6) 判据=$NC(应15)；或场景包/负例提交缺失"
fi

# ── [2/7] 自评量表覆盖六阶段全部退出标准 ───────────────────────
# 实施计划原文：「自评量表覆盖六阶段全部退出标准」。
# 阶段名以第 2 章 2.2 节表格为准（发现/定界/V0/评估/推广/采用），
# 不是「构建/验证/上线」这类通用生命周期叫法。
python3 -m src.rubric --criteria fixtures/exit_criteria.json --out results 2>results/rubric.err >/dev/null
D2=$(python3 - <<'PY' 2>&1
import json, sys
try:
    r = json.load(open("results/rubric.json"))
except Exception as e:
    print(f"BAD 读不到 results/rubric.json（{e}）"); sys.exit()
crit = json.load(open("fixtures/exit_criteria.json"))
want = {c["id"] for p in crit["phases"] for c in p["criteria"]}
want_ph = {p["id"] for p in crit["phases"]}
got = {i["criterion_id"] for i in r.get("items", [])}
got_ph = {i.get("phase_id") for i in r.get("items", [])}
probs = []
if want - got:
    probs.append("量表漏了这些退出标准：" + "、".join(sorted(want - got)))
if want_ph - got_ph:
    probs.append("量表漏了这些阶段：" + "、".join(sorted(want_ph - got_ph)))
print("BAD " + "；".join(probs) if probs else
      f"OK 6 个阶段 / {len(want)} 条退出标准全部覆盖")
PY
)
if [ "${D2:0:2}" = "OK" ]; then ok 2 "量表覆盖全部退出标准" "${D2:3}"
else bad 2 "量表覆盖全部退出标准" "${D2:4} $(head -c 80 results/rubric.err 2>/dev/null)"; fi

# ── [3/7] 量表判据可判定 ───────────────────────────────────────
# 第 2 章：退出标准必须能用「是/否」回答。「需求明确了」「客户满意了」
# 这类表述不能作为退出标准——量表本身也不许出现这种措辞。
D3=$(python3 - <<'PY' 2>&1
import json, re, sys
try:
    r = json.load(open("results/rubric.json"))
except Exception:
    print("BAD 无 rubric.json，见第 2 项"); sys.exit()
vague = ["应该没问题", "基本完成", "大致", "差不多", "心里有数", "客户满意了", "需求明确了"]
probs = []
for i in r.get("items", []):
    q = str(i.get("question", "")) + str(i.get("evidence_required", ""))
    if not q.strip():
        probs.append(f"{i.get('criterion_id')} 没有可判定的问法"); continue
    hit = [v for v in vague if v in q]
    if hit:
        probs.append(f"{i.get('criterion_id')} 用了模糊措辞「{hit[0]}」")
    if not i.get("evidence_required"):
        probs.append(f"{i.get('criterion_id')} 没写清要拿什么证据来判")
print("BAD " + "；".join(probs[:2]) if probs else
      f"OK {len(r.get('items', []))} 条判据均为是/否问法且写明了所需证据")
PY
)
if [ "${D3:0:2}" = "OK" ]; then ok 3 "量表判据可判定" "${D3:3}"
else bad 3 "量表判据可判定" "${D3:4}"; fi

# ── [4/7] 参考实现能跑通完整闭环 ───────────────────────────────
RUN=$(python3 -m src.pipeline --scenario fixtures/scenario --out results 2>results/pipeline.err)
if echo "$RUN" | grep -q 'closed_loop=true'; then
    ok 4 "参考实现跑通闭环" "$RUN"
else
    bad 4 "参考实现跑通闭环" "${RUN:-无输出}，要求打印 closed_loop=true。\
$(head -c 100 results/pipeline.err 2>/dev/null)"
fi

# ── [5/7] 闭环真的闭合 ─────────────────────────────────────────
# 六个孤立脚本各跑各的也能打印 closed_loop=true。这一项要求每个阶段的
# 产出确实被下一个阶段读走了——链条不断裂，才叫闭环。
D5=$(python3 - <<'PY' 2>&1
import json, sys
try:
    r = json.load(open("results/pipeline.json"))
except Exception as e:
    print(f"BAD 读不到 results/pipeline.json（{e}）"); sys.exit()
stages = r.get("stages", [])
if len(stages) < 6:
    print(f"BAD 只有 {len(stages)} 个阶段，应为 6"); sys.exit()
probs = []
for prev, cur in zip(stages, stages[1:]):
    outs = set(prev.get("outputs") or [])
    ins = set(cur.get("consumes") or [])
    if not (outs & ins):
        probs.append(f"{cur.get('phase_id')} 没有消费 {prev.get('phase_id')} 的任何产出，链条在这里断了")
print("BAD " + "；".join(probs[:2]) if probs else
      "OK 6 个阶段首尾相接，每一阶段都消费了上一阶段的产出")
PY
)
if [ "${D5:0:2}" = "OK" ]; then ok 5 "闭环真的闭合" "${D5:3}"
else bad 5 "闭环真的闭合" "${D5:4}"; fi

# ── [6/7] 参考实现能通过自评量表 ───────────────────────────────
SCORE=$(python3 -m src.rubric --criteria fixtures/exit_criteria.json \
        --submission results/submission.md --out results --tag ref 2>results/score.err)
D6=$(python3 - <<'PY' 2>&1
import json, sys
try:
    r = json.load(open("results/score_ref.json"))
except Exception as e:
    print(f"BAD 读不到 results/score_ref.json（{e}）"); sys.exit()
if not r.get("passed"):
    fails = [i["criterion_id"] for i in r.get("items", []) if not i.get("met")]
    print(f"BAD 参考实现自己都没通过量表，未达标 {len(fails)} 条：" + "、".join(fails[:5])); sys.exit()
print(f"OK 参考实现通过全部 {len(r.get('items', []))} 条退出标准")
PY
)
if [ "${D6:0:2}" = "OK" ]; then ok 6 "参考实现通过量表" "${D6:3}"
else bad 6 "参考实现通过量表" "${D6:4}｜${SCORE:-无输出}"; fi

# ── [7/7] 量表能判掉残缺提交（负例，硬门禁） ───────────────────
# 这一项直接来自第 26 章自检题第 3 问：「自评量表如果只覆盖了六阶段中的
# 构建和验证两个阶段，其余四个阶段用『应该没问题』带过，能不能算通过？」
# 参考答案是不能。那就让量表真的判得出来——一个只会打通过的量表毫无价值。
BADS=$(python3 -m src.rubric --criteria fixtures/exit_criteria.json \
       --submission fixtures/bad_submission/self_assessment.md --out results --tag bad 2>results/badscore.err)
D7=$(python3 - <<'PY' 2>&1
import json, sys
try:
    r = json.load(open("results/score_bad.json"))
except Exception as e:
    print(f"BAD 读不到 results/score_bad.json（{e}）"); sys.exit()
if r.get("passed"):
    print("BAD 量表把那份用「应该没问题」带过四个阶段的提交判成了通过——一个只会打通过的量表毫无价值"); sys.exit()
unmet = [i for i in r.get("items", []) if not i.get("met")]
if len(unmet) < 5:
    print(f"BAD 只判出 {len(unmet)} 条未达标。那份提交的发现/定界/推广/采用四个阶段基本是空的，"
          "外加 V0 用 mock 数据、评估未签字，应当判出明显更多"); sys.exit()
# 还要能说清缺在哪，而不是只给一个分数
if not any(i.get("reason") for i in unmet):
    print("BAD 判了不通过但没说明每条为什么不达标。只给分数的量表指导不了改进"); sys.exit()
print(f"OK 判为不通过，指出 {len(unmet)} 条未达标并逐条给出理由")
PY
)
if [ "${D7:0:2}" = "OK" ]; then ok 7 "量表能判掉残缺提交" "${D7:3}"
else bad 7 "量表能判掉残缺提交" "${D7:4}｜${BADS:-无输出}"; fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
