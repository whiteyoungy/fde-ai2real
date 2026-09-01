#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-05 验收脚本。
#
# 5 项检查，每项打印一行人类可读结果；全部 OK 且以 exit code 0 结束才算通过。
# 核心验收在第 5 项：故意引入劣化 -> 门禁必须阻断；恢复 -> 门禁必须放行。
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
LAB_DIR="$(pwd)"
export PYTHONPATH="$LAB_DIR:${PYTHONPATH:-}"

RESULTS_DIR="$LAB_DIR/results"
mkdir -p "$RESULTS_DIR"
rm -f "$RESULTS_DIR"/verify_*.json

PASS=0
FAIL=0

ok() {
    echo "[$1/5] $2 ......... OK${3:+ ($3)}"
    PASS=$((PASS + 1))
}

bad() {
    echo "[$1/5] $2 ......... FAIL${3:+ ($3)}"
    FAIL=$((FAIL + 1))
}

PY=python3

echo "== Lab-05 评估框架验收 =="
echo

# ---------------------------------------------------------------------------
# [1/5] 三层评估集加载
# ---------------------------------------------------------------------------
LOAD_OUT=$($PY -m src.dataset_check 2>&1)
LOAD_RC=$?
if [ $LOAD_RC -eq 0 ]; then
    ok 1 "三层评估集加载" "$LOAD_OUT"
else
    bad 1 "三层评估集加载" "$LOAD_OUT"
fi

# ---------------------------------------------------------------------------
# [2/5] 确定性评分器自检
# ---------------------------------------------------------------------------
SCORER_OUT=$($PY -m src.scorer_selftest 2>&1)
SCORER_RC=$?
if [ $SCORER_RC -eq 0 ]; then
    ok 2 "确定性评分器" "$SCORER_OUT"
else
    bad 2 "确定性评分器" "$SCORER_OUT"
fi

# ---------------------------------------------------------------------------
# [3/5] LLM-as-Judge 偏差缓解（成对比较 + 顺序打乱）
#   有 key: 要求正/反两次顺序判断一致，且判给更忠实的答案
#   无 key: 只要求跑通、能解析出胜者、顺序确实被打乱
# ---------------------------------------------------------------------------
JUDGE_OUT=$($PY -m src.judge_selftest 2>&1)
JUDGE_RC=$?
if [ $JUDGE_RC -eq 0 ]; then
    ok 3 "LLM-as-Judge 偏差缓解" "$JUDGE_OUT"
else
    bad 3 "LLM-as-Judge 偏差缓解" "$JUDGE_OUT"
fi

# ---------------------------------------------------------------------------
# [4/5] 基线评估
# ---------------------------------------------------------------------------
BASELINE_JSON="$RESULTS_DIR/verify_baseline.json"
BASE_OUT=$($PY -m src.run_eval --config configs/system_baseline.yaml --output "$BASELINE_JSON" --summary 2>&1)
BASE_RC=$?
if [ $BASE_RC -eq 0 ]; then
    ok 4 "基线评估" "$(echo "$BASE_OUT" | tail -1)"
else
    bad 4 "基线评估" "$BASE_OUT"
fi

# ---------------------------------------------------------------------------
# [5/5] 门禁有效性：劣化必须被阻断，恢复后必须放行
# ---------------------------------------------------------------------------
GATE5_OK=1
GATE5_MSG=""

$PY -m src.gate --results "$BASELINE_JSON" --thresholds configs/thresholds.yaml >/tmp/gate_baseline.$$ 2>&1
GATE_BASE_RC=$?
if [ $GATE_BASE_RC -ne 0 ]; then
    GATE5_OK=0
    GATE5_MSG="基线本身就被门禁阻断了（不应该）：$(cat /tmp/gate_baseline.$$)"
fi

DEGRADED_JSON="$RESULTS_DIR/verify_degraded.json"
$PY -m src.run_eval --config configs/system_degraded.yaml --output "$DEGRADED_JSON" --summary >/tmp/eval_degraded.$$ 2>&1
$PY -m src.gate --results "$DEGRADED_JSON" --baseline "$BASELINE_JSON" --thresholds configs/thresholds.yaml >/tmp/gate_degraded.$$ 2>&1
GATE_DEGRADED_RC=$?
if [ $GATE_DEGRADED_RC -eq 0 ]; then
    GATE5_OK=0
    GATE5_MSG="劣化版本没有被门禁阻断（应该阻断）"
fi

RESTORED_JSON="$RESULTS_DIR/verify_restored.json"
$PY -m src.run_eval --config configs/system_baseline.yaml --output "$RESTORED_JSON" --summary >/tmp/eval_restored.$$ 2>&1
$PY -m src.gate --results "$RESTORED_JSON" --baseline "$BASELINE_JSON" --thresholds configs/thresholds.yaml >/tmp/gate_restored.$$ 2>&1
GATE_RESTORED_RC=$?
if [ $GATE_RESTORED_RC -ne 0 ]; then
    GATE5_OK=0
    GATE5_MSG="恢复基线后门禁仍然阻断（应该放行）：$(cat /tmp/gate_restored.$$)"
fi

if [ $GATE5_OK -eq 1 ]; then
    ok 5 "门禁有效性" "劣化被阻断: $(grep -m1 'reason' /tmp/gate_degraded.$$ | head -c 60), 恢复后放行"
else
    bad 5 "门禁有效性" "$GATE5_MSG"
fi

rm -f /tmp/gate_baseline.$$ /tmp/gate_degraded.$$ /tmp/gate_restored.$$ /tmp/eval_degraded.$$ /tmp/eval_restored.$$

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="

# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 5。
if [ $FAIL -eq 0 ] && [ $PASS -eq 5 ]; then
    echo "验收通过。"
    exit 0
else
    echo "验收未通过：通过 $PASS/5，失败 $FAIL。少于 5 项说明有检查未执行完。"
    exit 1
fi
