#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-09 国产栈演练 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] && PATH="$PWD/.venv/bin:$PATH"

OLLAMA=${OLLAMA:-http://127.0.0.1:11434}
PASS=0; FAIL=0
ok()  { printf '[%s/7] %-28s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-28s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

echo "== Lab-09 国产栈演练 验收 =="
echo
mkdir -p results; rm -f results/selection.json results/vram_budget.md results/ascend_deploy.md

# ── [1/7] 夹具与本地模型就位 ───────────────────────────────────
NM=$(python3 -c "import json;print(len(json.load(open('fixtures/models.json'))['models']))" 2>/dev/null || echo 0)
NS=$(python3 -c "import json;print(len(json.load(open('fixtures/scenarios.json'))['scenarios']))" 2>/dev/null || echo 0)
OV=$(curl -s --max-time 5 "$OLLAMA/api/version" | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])' 2>/dev/null || echo "")
if [ "$NM" -eq 5 ] && [ "$NS" -eq 4 ] && [ -n "$OV" ]; then
    ok 1 "夹具与本地模型就位" "模型 $NM 个 / 场景 $NS 个；ollama $OV"
else
    bad 1 "夹具与本地模型就位" "模型=$NM(应5) 场景=$NS(应4) ollama='${OV:-连不上}'"
fi

SEL=$(python3 -m src.select --models fixtures/models.json --scenarios fixtures/scenarios.json --out results 2>results/select.err)

# ── [2/7] 选型结果全部正确 ─────────────────────────────────────
D2=$(python3 - <<'PY' 2>&1
import json, sys
try:
    got = json.load(open("results/selection.json"))
except Exception as e:
    print(f"BAD 读不到 results/selection.json（{e}）"); sys.exit()
exp = {s["id"]: s["expect"] for s in json.load(open("fixtures/scenarios.json"))["scenarios"]}
picks = {r["scenario_id"]: r.get("selected") for r in got.get("results", [])}
wrong = [f"{k} 选了 {picks.get(k, '缺')}（应为 {v or '可行集为空'}）"
         for k, v in exp.items() if picks.get(k, "缺") != v]
print("BAD " + "；".join(wrong[:3]) if wrong else
      "OK " + "、".join(f"{k}→{v or '空'}" for k, v in exp.items()))
PY
)
if [ "${D2:0:2}" = "OK" ]; then ok 2 "选型结果全部正确" "${D2:3}"
else bad 2 "选型结果全部正确" "${D2:4}｜${SEL:-无输出} $(head -c 80 results/select.err 2>/dev/null)"; fi

# ── [3/7] 商用场景零容忍选中研究许可档（硬门禁） ───────────────
# 第 23 章把这条列为「最需要记住的一条硬约束」：Qwen2.5-3B 用的是
# RESEARCH LICENSE，不可商用，而同系列 72B 那份允许商用——
# 档位相邻不代表授权条款相邻。选错的代价不是效果差，是法务问题。
D3=$(python3 - <<'PY' 2>&1
import json, sys
try:
    got = json.load(open("results/selection.json"))
except Exception:
    print("BAD 无 selection.json，见第 2 项"); sys.exit()
models = {m["id"]: m for m in json.load(open("fixtures/models.json"))["models"]}
scen = {s["id"]: s for s in json.load(open("fixtures/scenarios.json"))["scenarios"]}
bad = []
for r in got.get("results", []):
    sid, pick = r["scenario_id"], r.get("selected")
    if not pick:
        continue
    if scen[sid]["constraints"].get("commercial_use") and not models[pick]["commercial_use"]:
        bad.append(f"{sid} 商用场景选了不可商用的 {pick}（{models[pick]['license']}）")
print("BAD " + "；".join(bad) if bad else
      "OK 所有商用场景均未选中研究许可档位")
PY
)
if [ "${D3:0:2}" = "OK" ]; then ok 3 "商用场景避开研究许可" "${D3:3}"
else bad 3 "商用场景避开研究许可" "${D3:4}。这不是效果问题，是法务问题，一次都不许"; fi

# ── [4/7] 可行集为空时不许硬凑 ─────────────────────────────────
D4=$(python3 - <<'PY' 2>&1
import json, sys
try:
    got = json.load(open("results/selection.json"))
except Exception:
    print("BAD 无 selection.json，见第 2 项"); sys.exit()
r = next((x for x in got.get("results", []) if x["scenario_id"] == "s3"), None)
if r is None:
    print("BAD selection.json 里没有 s3 的结果"); sys.exit()
if r.get("selected"):
    print(f"BAD s3 硬凑了一个 {r['selected']}——可行集为空时应当返回空并说明该谈判什么"); sys.exit()
neg = (r.get("negotiation") or r.get("advice") or "")
if len(str(neg)) < 15:
    print("BAD s3 返回了空，但没给出谈判建议。只说「无解」对客户没有价值")
else:
    print(f"OK s3 可行集为空且给出谈判建议：{str(neg)[:60]}")
PY
)
if [ "${D4:0:2}" = "OK" ]; then ok 4 "无解时不硬凑" "${D4:3}"
else bad 4 "无解时不硬凑" "${D4:4}"; fi

# ── [5/7] CPU 路径实测跑通 ─────────────────────────────────────
# 实施计划原文：「CPU 路径必须实测跑通」。这一项要真调模型，不接受任何模拟。
DEP=$(python3 -m src.deploy_cpu --backend "$OLLAMA" 2>results/deploy.err)
TOK=$(echo "$DEP" | grep -o 'tokens=[0-9]*' | head -1 | cut -d= -f2)
if echo "$DEP" | grep -q 'ok=true' && [ "${TOK:-0}" -ge 1 ] 2>/dev/null; then
    ok 5 "CPU 路径实测跑通" "$DEP"
else
    bad 5 "CPU 路径实测跑通" "${DEP:-无输出}，要求 ok=true 且 tokens≥1（必须真调模型）。\
$(head -c 80 results/deploy.err 2>/dev/null)"
fi

# ── [6/7] 显存预算表标注来源且估算值上浮 ───────────────────────
python3 -m src.vram_budget --models fixtures/models.json --out results 2>results/vram.err >/dev/null
python3 -m src.ascend_doc --out results 2>results/ascend.err >/dev/null
D6=$(python3 - <<'PY' 2>&1
import json, pathlib, re, sys
p = pathlib.Path("results/vram_budget.md")
if not p.exists():
    print("BAD 没有产出 results/vram_budget.md"); sys.exit()
t = p.read_text(encoding="utf-8")
models = json.load(open("fixtures/models.json"))["models"]
probs = []
for m in models:
    if m["name"] not in t and m["id"] not in t:
        probs.append(f"预算表里没有 {m['id']}")
if not re.search(r"官方", t) or not re.search(r"估算", t):
    probs.append("没有区分「官方给出」与「按参数量估算」两种口径")
# 估算值必须上浮 ≥20%：表里应出现每个估算模型上浮后的数字
for m in models:
    if m["vram_gb"]["basis"] == "估算":
        need = m["vram_gb"]["value"] * 1.2
        # 分组必须包住整个候选集：写成 \b{a}|{b}|{c}\b 时 | 作用于整个模式，
        # \b 只锚住首尾两个分支，中间的会被文档里任意一处 "7B" 之类命中，检查形同虚设。
        if not re.search(rf"\b(?:{int(need)}|{need:.1f}|{int(need)+1})\b", t):
            probs.append(f"{m['id']} 估算 {m['vram_gb']['value']}GB 未见 ≥20% 上浮后的数字（应 ≥{need:.0f}GB）")
            break
print("BAD " + "；".join(probs[:2]) if probs else
      f"OK 5 个档位齐备，区分官方/估算口径，估算值均按 ≥20% 上浮")
PY
)
if [ "${D6:0:2}" = "OK" ]; then ok 6 "显存预算表口径清晰" "${D6:3}"
else bad 6 "显存预算表口径清晰" "${D6:4}"; fi

# ── [7/7] 昇腾路径诚实标注，且未实测标注不被滥用 ───────────────
# 实施计划原文：「昇腾路径若无硬件，README 明确标注为『基于官方文档的
# 流程说明，未实测』，不假装已验证」。这条验收标准本身就是可机器检查的。
#
# 但只查「有没有写未实测」是不够的——那样满篇都标未实测也能过。
# 所以同时查它没被滥用：CPU 路径是实测跑通的，不许也标成未实测。
# 查的是实现方产出的昇腾部署说明，不是本 Lab 自带的 README——
# 查自己写的文档等于自己给自己判分。
D7=$(python3 - <<'PY' 2>&1
import pathlib, re, sys
p = pathlib.Path("results/ascend_deploy.md")
if not p.exists():
    print("BAD 没有产出 results/ascend_deploy.md"); sys.exit()
t = p.read_text(encoding="utf-8")
probs = []
# 昇腾段落必须有明确的未实测标注
m = re.search(r"(昇腾|Ascend|CANN)[\s\S]{0,1200}", t)
if not m:
    probs.append("ascend_deploy.md 里没有昇腾相关内容")
else:
    seg = m.group(0)
    if not re.search(r"未实测|没有实测|未经实测|未验证", seg):
        probs.append("昇腾段落没有明确的「未实测」标注——无硬件时不假装已验证是本 Lab 的验收标准之一")
    if not re.search(r"官方文档|官方仓库|官方说明", seg):
        probs.append("昇腾段落没说明依据来源（应写明「基于官方文档的流程说明」）")
# 对偶检查：CPU 路径是实测跑通的，不许标成未实测。
# 只查「有没有写未实测」的话，满篇都标未实测也能过——那是用免责声明
# 替代验证，比不写更坏。
c = re.search(r"(CPU\s*(降级|路径)|纯\s*CPU)[\s\S]{0,600}", t)
if c and re.search(r"未实测|未验证", c.group(0)):
    probs.append("CPU 路径被标成了未实测——它是实测跑通的（见第 5 项），标注不能滥用")
print("BAD " + "；".join(probs[:2]) if probs else
      "OK 昇腾路径明确标注未实测并说明依据；CPU 路径未被误标")
PY
)
if [ "${D7:0:2}" = "OK" ]; then ok 7 "未实测标注诚实且不滥用" "${D7:3}"
else bad 7 "未实测标注诚实且不滥用" "${D7:4}"; fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
