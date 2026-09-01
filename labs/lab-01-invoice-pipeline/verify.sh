#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-01 脏 PDF 发票摄取管道 · 验收脚本
#
# 6 项检查，全部 OK 且 exit 0 才算通过。
# 注意：测退出码不要放进管道（`verify.sh | tail; echo $?` 拿到的是 tail 的退出码）。
#       正确用法：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

PASS=0; FAIL=0
ok()  { printf '[%s/6] %-26s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/6] %-26s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

echo "== Lab-01 脏 PDF 发票摄取管道 验收 =="
echo

# 模型路径：有 DEEPSEEK_API_KEY 走 API，否则降级本地 Ollama
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    MODE="API（deepseek-chat）"; STRICT=1
else
    MODE="本地降级（qwen2.5:0.5b）"; STRICT=0
fi
echo "模型路径：$MODE"
echo

OUT="results"
rm -rf "$OUT"; mkdir -p "$OUT"

# ── [1/6] 夹具完整性 ───────────────────────────────────────────
N_PDF=$(ls fixtures/pdfs/*.pdf 2>/dev/null | wc -l)
N_MAN=$(python3 -c "import json;print(len(json.load(open('fixtures/expected/manifest.json'))))" 2>/dev/null || echo 0)
if [ "$N_PDF" -eq 10 ] && [ "$N_MAN" -eq 10 ]; then
    ok 1 "夹具完整性" "10 份 PDF / 10 条 manifest"
else
    bad 1 "夹具完整性" "PDF=$N_PDF manifest=$N_MAN，应各为 10；先跑 python3 fixtures/generate.py"
fi

# ── [2/6] 管道可运行 ───────────────────────────────────────────
if python3 -m src.run_pipeline --input fixtures/pdfs --out "$OUT" > "$OUT/run.log" 2>&1; then
    ok 2 "管道可运行" "已产出 $OUT/"
else
    bad 2 "管道可运行" "$(tail -1 "$OUT/run.log" 2>/dev/null | cut -c1-90)"
fi

# ── [3/6] 成功件数量 ≥8/10 ─────────────────────────────────────
# 说明：7 份脏但可解析的必须全过；3 份破损件不计入成功。
#       ≥8 的口径是"10 份里至少 8 份被正确归类"，见 README 验收标准。
CLS=$(python3 -m src.check_results --out "$OUT" --manifest fixtures/expected/manifest.json --mode classify 2>/dev/null)
if [ -n "$CLS" ] && [ "${CLS%%/*}" -ge 8 ] 2>/dev/null; then
    ok 3 "归类正确率" "$CLS"
else
    bad 3 "归类正确率" "${CLS:-无输出}，要求 ≥8/10"
fi

# ── [4/6] 破损件全部隔离，未污染下游 ───────────────────────────
Q=$(python3 -m src.check_results --out "$OUT" --manifest fixtures/expected/manifest.json --mode quarantine 2>/dev/null)
if [ "$Q" = "3/3" ]; then
    ok 4 "破损件隔离" "3 份全部进隔离队列，未进 clean 输出"
else
    bad 4 "破损件隔离" "${Q:-无输出}，要求 3/3；破损件混入下游即为致命失败"
fi

# ── [5/6] 字段抽取准确性 ───────────────────────────────────────
# 有 key 时校验字段值与 manifest.expect 一致；无 key 时只校验 schema 合规。
if [ "$STRICT" -eq 1 ]; then
    F=$(python3 -m src.check_results --out "$OUT" --manifest fixtures/expected/manifest.json --mode fields 2>/dev/null)
    THRESH="7/7"
    HINT="有 key 模式：7 份脏件的字段值必须与 manifest 完全一致"
else
    F=$(python3 -m src.check_results --out "$OUT" --manifest fixtures/expected/manifest.json --mode schema 2>/dev/null)
    THRESH="7/7"
    HINT="无 key 模式：只校验输出符合 schema，不要求字段值正确（0.5B 抽不准是预期的）"
fi
if [ "$F" = "$THRESH" ]; then
    ok 5 "字段抽取" "$F（$HINT）"
else
    bad 5 "字段抽取" "${F:-无输出}，要求 $THRESH。$HINT"
fi

# ── [6/6] 自纠错循环真的发生过 ─────────────────────────────────
# 本 Lab 的核心机制：校验失败时把错误与堆栈回灌进模型上下文重试。
# 必须有证据表明至少发生过一次「首轮校验失败 → 回灌 → 再次尝试」。
R=$(python3 -m src.check_results --out "$OUT" --mode retries 2>/dev/null)
if [ -n "$R" ] && [ "${R%% *}" -ge 1 ] 2>/dev/null; then
    ok 6 "自纠错循环" "$R"
else
    bad 6 "自纠错循环" "${R:-无输出}，需有 ≥1 次校验失败后回灌重试的记录"
fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 6。
if [ $FAIL -eq 0 ] && [ $PASS -eq 6 ]; then
    echo "验收通过。"
    exit 0
else
    echo "验收未通过：通过 $PASS/6，失败 $FAIL。少于 6 项说明有检查未执行完。"
    exit 1
fi
