#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-04 混合检索 RAG + 检索质量诊断 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

# 本 Lab 的依赖装在 .venv 里。不做这一步的话，忘记 activate 的读者会看到
# 一连串 "No module named src.xxx" 的假失败，误以为是实现有问题。
[ -x .venv/bin/python ] && PATH="$PWD/.venv/bin:$PATH"

QPORT=16333
QURL="http://127.0.0.1:$QPORT"
CNAME=lab04-qdrant
PASS=0; FAIL=0
ok()  { printf '[%s/7] %-26s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-26s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

cleanup() { docker rm -f "$CNAME" >/dev/null 2>&1; }
trap cleanup EXIT

echo "== Lab-04 混合检索 RAG + 检索质量诊断 验收 =="
echo
mkdir -p results

# ── [1/7] 夹具完整 ─────────────────────────────────────────────
ND=$(grep -c . fixtures/docs.jsonl 2>/dev/null || echo 0)
NQ=$(grep -c . fixtures/queries.jsonl 2>/dev/null || echo 0)
NC=$(grep -c . fixtures/diagnose_cases.jsonl 2>/dev/null || echo 0)
if [ "$ND" -eq 1241 ] && [ "$NQ" -eq 59 ] && [ "$NC" -eq 5 ]; then
    ok 1 "夹具完整" "文档 $ND 篇 / 查询 $NQ 条 / 诊断用例 $NC 条"
else
    bad 1 "夹具完整" "文档=$ND(应1241) 查询=$NQ(应59) 诊断=$NC(应5)。先跑 python3 fixtures/generate.py"
fi

# ── 拉起 Qdrant ────────────────────────────────────────────────
cleanup
docker run -d --name "$CNAME" -p $QPORT:6333 qdrant/qdrant:latest >/dev/null 2>&1
for _ in $(seq 1 20); do
    curl -s --max-time 2 "$QURL/" >/dev/null 2>&1 && break
    sleep 1
done
QV=$(curl -s --max-time 3 "$QURL/" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("version","?"))' 2>/dev/null || echo "?")

# ── [2/7] Qdrant 索引就绪 ──────────────────────────────────────
IDX=$(python3 -m src.index --qdrant "$QURL" 2>results/index.err)
NPT=$(curl -s --max-time 5 "$QURL/collections" \
      | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["result"]["collections"]))' 2>/dev/null || echo 0)
if echo "$IDX" | grep -q 'indexed=1241' && [ "${NPT:-0}" -ge 1 ]; then
    ok 2 "Qdrant 索引就绪" "qdrant $QV；$IDX"
else
    bad 2 "Qdrant 索引就绪" "${IDX:-无输出}（qdrant $QV，集合数 $NPT）；要求 indexed=1241。$(head -c 80 results/index.err 2>/dev/null)"
fi

# ── [3/7] 三路基线可复现 ───────────────────────────────────────
EV=$(python3 -m src.evaluate --qdrant "$QURL" --out results 2>results/eval.err)
BM=$(echo "$EV" | grep -o 'bm25=[0-9]*' | cut -d= -f2)
VE=$(echo "$EV" | grep -o 'vector=[0-9]*' | cut -d= -f2)
HY=$(echo "$EV" | grep -o 'hybrid=[0-9]*' | cut -d= -f2)
if [ -n "${BM:-}" ] && [ -n "${VE:-}" ] && [ -n "${HY:-}" ]; then
    ok 3 "三路基线可复现" "$EV"
else
    bad 3 "三路基线可复现" "${EV:-无输出}，需打印 bm25=N vector=N hybrid=N（N 为 Recall@5 命中数，满分 59）。\
$(head -c 100 results/eval.err 2>/dev/null)"
fi

# ── [4/7] 混合显著优于纯向量基线（核心验收） ───────────────────
# 实施计划原文：「混合检索的 Recall@5 显著优于纯向量基线」。
# 「显著」在这里量化为至少高出 5 个百分点（59 条即至少多命中 3 条），
# 并要求混合不低于 BM25——否则「不如直接只用 BM25」。
if [ -n "${HY:-}" ] && [ -n "${VE:-}" ] && [ -n "${BM:-}" ]; then
    DIFF=$(( (HY - VE) * 100 / 59 ))
    if [ "$HY" -gt "$VE" ] && [ "$DIFF" -ge 5 ] && [ "$HY" -ge "$BM" ]; then
        ok 4 "混合优于纯向量" "混合 $HY/59 vs 纯向量 $VE/59（+${DIFF}pp），且不低于 BM25 $BM/59"
    else
        bad 4 "混合优于纯向量" "混合 $HY/59 纯向量 $VE/59（+${DIFF}pp）BM25 $BM/59。\
要求高出纯向量 ≥5pp 且 ≥BM25。若混合夹在两者之间，先检查 RRF 是否在完整排序上做的——应各取 top-50 截断后再融合"
    fi
else
    bad 4 "混合优于纯向量" "第 3 项未产出可比数值"
fi

# ── [5/7] 互补性成立 ───────────────────────────────────────────
# 防的是「BM25 一家独大、混合只是搭便车」——只看总分会被蒙混过去。
D5=$(python3 - <<'PY' 2>&1
import json, sys
try:
    r = json.load(open("results/report.json"))
except Exception as e:
    print(f"BAD 读不到 results/report.json（{e}）；evaluate 需产出分类别报告"); sys.exit()
try:
    by = r["by_kind"]
    sem, bur = by["semantic"], by["buried_id"]
    gv, gb = sem["vector"], sem["bm25"]
    hv, hb = bur["vector"], bur["bm25"]
except Exception as e:
    print(f"BAD report.json 缺字段 {e}；需含 by_kind.<类型>.{{bm25,vector,hybrid}}"); sys.exit()
probs = []
if not gv > gb:
    probs.append(f"semantic 类未体现向量优势（向量{gv} vs BM25{gb}）")
if not hb > hv:
    probs.append(f"buried_id 类未体现 BM25 优势（BM25{hb} vs 向量{hv}）")
print("BAD " + "；".join(probs) if probs else
      f"OK semantic 向量{gv}>BM25{gb}；buried_id BM25{hb}>向量{hv}，两路失败集确实不相交")
PY
)
if [ "${D5:0:2}" = "OK" ]; then ok 5 "互补性成立" "${D5:3}"
else bad 5 "互补性成立" "${D5:4}"; fi

# ── [6/7] Rerank 生效 ──────────────────────────────────────────
RR=$(python3 -m src.evaluate --qdrant "$QURL" --mode rerank --out results 2>results/rerank.err)
if echo "$RR" | grep -q 'improved=yes'; then
    ok 6 "Rerank 生效" "$RR"
else
    bad 6 "Rerank 生效" "${RR:-无输出}，需打印 hybrid_mrr=.. rerank_mrr=.. improved=yes。\
$(head -c 80 results/rerank.err 2>/dev/null)"
fi

# ── [7/7] 三分法归因正确 ───────────────────────────────────────
DG=$(python3 -m src.diagnose --qdrant "$QURL" --cases fixtures/diagnose_cases.jsonl 2>results/diag.err)
DC=$(echo "$DG" | grep -o 'correct=[0-9]*' | cut -d= -f2)
if [ "${DC:-0}" -eq 5 ] 2>/dev/null; then
    ok 7 "三分法归因正确" "$DG"
else
    bad 7 "三分法归因正确" "${DG:-无输出}，要求 correct=5（四种根因各一条，外加一条本就正确、不该被报错的）。\
$(head -c 100 results/diag.err 2>/dev/null)"
fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
