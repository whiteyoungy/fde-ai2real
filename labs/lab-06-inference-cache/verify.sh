#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-06 私有化推理 + 量化 + 语义缓存 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

# 依赖装在 .venv 里。不做这一步，忘记 activate 的读者会看到一连串
# "No module named src.xxx" 的假失败，误以为是实现有问题。
[ -x .venv/bin/python ] && PATH="$PWD/.venv/bin:$PATH"

OLLAMA=${OLLAMA:-http://127.0.0.1:11434}
P95_BUDGET_MS=${P95_BUDGET_MS:-20000}   # CPU 档默认放得很宽，有 GPU 时用环境变量收紧
PASS=0; FAIL=0
ok()  { printf '[%s/7] %-26s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-26s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

echo "== Lab-06 私有化推理 + 量化 + 语义缓存 验收 =="
echo

if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    TIER=api;   HIT_MIN=6; FALSE_MAX=0
    echo "档位：有 key（三层全开）——命中率 ≥${HIT_MIN}/10，误命中必须为 0"
else
    TIER=nokey; HIT_MIN=5; FALSE_MAX=2
    echo "档位：无 key（仅第 1、2 层）——命中率 ≥${HIT_MIN}/10，误命中 ≤${FALSE_MAX}"
    echo "!! 本档配置不安全，只用于跑通链路。实测证明没有第 3 层裁判，"
    echo "!! 纯 embedding 在本夹具上任何阈值都做不到零误命中。不要照搬到生产。"
fi
echo
mkdir -p results

# ── [1/7] 夹具与模型就位 ───────────────────────────────────────
NP=$(grep -c . fixtures/cache_pairs.jsonl 2>/dev/null || echo 0)
NH=$(grep -c '"expect": "hit"'  fixtures/cache_pairs.jsonl 2>/dev/null || echo 0)
NM=$(grep -c '"expect": "miss"' fixtures/cache_pairs.jsonl 2>/dev/null || echo 0)
NQ=$(ollama list 2>/dev/null | grep -c 'qwen2.5:0.5b' || echo 0)
if [ "$NP" -eq 22 ] && [ "$NH" -eq 10 ] && [ "$NM" -eq 12 ] && [ "$NQ" -ge 2 ]; then
    ok 1 "夹具与模型就位" "22 对（应命中 $NH / 不该命中 $NM）；本地量化档位 $NQ 个"
else
    bad 1 "夹具与模型就位" "用例=$NP(应22) hit=$NH(应10) miss=$NM(应12) 模型档位=$NQ(应≥2)。\
缺模型请跑 ollama pull qwen2.5:0.5b 与 ollama pull qwen2.5:0.5b-instruct-q8_0"
fi

# ── [2/7] 推理后端可用 ─────────────────────────────────────────
OV=$(curl -s --max-time 5 "$OLLAMA/api/version" \
     | python3 -c 'import sys,json;print(json.load(sys.stdin).get("version","?"))' 2>/dev/null || echo "")
BASE=$(python3 -m src.serve --probe --backend "$OLLAMA" 2>results/serve.err)
if [ -n "$OV" ] && echo "$BASE" | grep -q 'baseline_ms='; then
    ok 2 "推理后端可用" "ollama $OV；$BASE"
else
    bad 2 "推理后端可用" "ollama 版本='${OV:-连不上}' 探针输出='${BASE:-无}'，需打印 baseline_ms=。\
$(head -c 80 results/serve.err 2>/dev/null)"
fi

# ── [3/7][4/7] 缓存命中率与误命中率 ────────────────────────────
CE=$(python3 -m src.cache_eval --pairs fixtures/cache_pairs.jsonl --backend "$OLLAMA" 2>results/cache.err)
HIT=$(echo "$CE" | grep -o 'hit=[0-9]*' | head -1 | cut -d= -f2)
FH=$(echo "$CE" | grep -o 'false_hit=[0-9]*' | head -1 | cut -d= -f2)

if [ "${HIT:-0}" -ge "$HIT_MIN" ] 2>/dev/null; then
    ok 3 "缓存命中率达标" "$CE（$TIER 档门槛 ≥$HIT_MIN/10）"
else
    bad 3 "缓存命中率达标" "${CE:-无输出}，要求 hit≥$HIT_MIN。$(head -c 80 results/cache.err 2>/dev/null)"
fi

# 本 Lab 的核心验收。误命中是把别人问题的答案自信地回给这个用户，
# 表现为一个流畅、完全错误的回答，而日志里命中率还很好看。
if [ -n "${FH:-}" ] && [ "${FH:-99}" -le "$FALSE_MAX" ] 2>/dev/null; then
    ok 4 "误命中受控" "false_hit=$FH（$TIER 档上限 $FALSE_MAX）"
else
    bad 4 "误命中受控" "false_hit=${FH:-无}，$TIER 档上限为 $FALSE_MAX。\
有 key 档必须为 0——若降不下来，多半是第 3 层裁判的 prompt 太宽松，没列清「什么算不等价」"
fi

# ── [5/7] 对照组证明护栏有效 ───────────────────────────────────
# 只看第 4 项的话，把阈值调到 0.99 也能让误命中变 0，但那时缓存等于没有。
# 这一项要求对照组与实验组同阈值，差别只在有没有护栏。
NV=$(python3 -m src.cache_eval --pairs fixtures/cache_pairs.jsonl --backend "$OLLAMA" --naive 2>results/naive.err)
NFH=$(echo "$NV" | grep -o 'false_hit=[0-9]*' | head -1 | cut -d= -f2)
NHIT=$(echo "$NV" | grep -o 'hit=[0-9]*' | head -1 | cut -d= -f2)
if [ -n "${NFH:-}" ] && [ -n "${FH:-}" ] && [ "$NFH" -gt "$FH" ] 2>/dev/null; then
    ok 5 "对照组证明护栏有效" "纯阈值 false_hit=$NFH（命中 $NHIT）→ 三层 false_hit=$FH（命中 $HIT）"
else
    bad 5 "对照组证明护栏有效" "纯阈值 false_hit=${NFH:-无} 三层 false_hit=${FH:-无}，\
要求纯阈值严格更多。若两者相同，通常是对照组没有与实验组用同一阈值"
fi

# ── [6/7] 压测显示缓存收益 ─────────────────────────────────────
BN=$(python3 -m src.bench --n 40 --backend "$OLLAMA" --out results 2>results/bench.err)
CP95=$(echo "$BN" | grep -o 'cold_p95_ms=[0-9]*' | head -1 | cut -d= -f2)
WP95=$(echo "$BN" | grep -o 'warm_p95_ms=[0-9]*' | head -1 | cut -d= -f2)
if [ -n "${CP95:-}" ] && [ -n "${WP95:-}" ] && [ "$WP95" -lt "$CP95" ] \
   && [ "$WP95" -lt "$P95_BUDGET_MS" ] 2>/dev/null; then
    ok 6 "压测显示缓存收益" "$BN（P95 预算 ${P95_BUDGET_MS}ms）"
else
    bad 6 "压测显示缓存收益" "${BN:-无输出}；冷 P95=${CP95:-?} 温 P95=${WP95:-?}，\
要求温 < 冷 且温 < ${P95_BUDGET_MS}ms。P95 没降通常是压测流量重复率太低"
fi

# ── [7/7] 量化档位对比 ─────────────────────────────────────────
QC=$(python3 -m src.quant_compare --backend "$OLLAMA" --out results 2>results/quant.err)
if echo "$QC" | grep -q 'models=2'; then
    ok 7 "量化档位对比" "$(echo "$QC" | tr '\n' ' ' | head -c 150)"
else
    bad 7 "量化档位对比" "${QC:-无输出}，需对比 q4 与 q8 并打印 models=2。\
$(head -c 80 results/quant.err 2>/dev/null)"
fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
