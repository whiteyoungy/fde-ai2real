#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-11 · 工作流发现演练 —— 结构校验脚本
#
# 这是一个文档型 Lab。本脚本只能做结构性校验：段落齐不齐、验收标准有没有
# 数字、范围外条款够不够多、有没有点出权限风险。它无法判断、也不假装能
# 判断你的内容对不对——真正的自评依据是 reference-answer.md，请务必对照它
# 再看一遍自己的产出。
#
# 用法：
#   ./verify.sh              校验 submission/scoping-document.md
#   ./verify.sh --example    校验 submission.example/scoping-document.md（讲师示范答卷）

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

MODE="submission"
if [[ "${1:-}" == "--example" ]]; then
  MODE="example"
fi

if [[ "$MODE" == "example" ]]; then
  TARGET="submission.example/scoping-document.md"
else
  TARGET="submission/scoping-document.md"
fi

PASS=0
FAIL=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }
info() { printf '%s\n' "$1"; }

info "=== Lab-11 工作流发现演练 · verify.sh（模式：$MODE） ==="
info ""

if [[ ! -f "$TARGET" ]]; then
  bad "找到 $TARGET"
  info ""
  if [[ "$MODE" == "example" ]]; then
    info "示范答卷缺失，这是 Lab 本身的问题，不是你的问题。请确认："
    info "  1. 是否在 lab-11-workflow-discovery/ 目录下执行本脚本"
    info "  2. submission.example/scoping-document.md 是否存在"
  else
    info "请先复制模板并填写，再运行本脚本："
    info ""
    info "    mkdir -p submission"
    info "    cp templates/scoping-document.md submission/scoping-document.md"
    info "    # ……填写 submission/scoping-document.md……"
    info "    ./verify.sh"
  fi
  info ""
  info "结果：0/1 检查通过（缺少产出文件，后续检查全部跳过）"
  exit 1
fi

ok "找到 $TARGET"

# ---------------------------------------------------------------------------
# 工具函数：提取指定关键词所在标题下的正文内容（不含标题本身）
# 规则：找到第一个标题行（# 开头）文字里包含关键词的行，记录其标题层级；
#       一直采集正文，直到遇到层级 <= 该层级的下一个标题行为止（或文件结尾）。
# ---------------------------------------------------------------------------
extract_section() {
  local file="$1" kw="$2"
  awk -v kw="$kw" '
    {
      if ($0 ~ /^#+/) {
        line = $0
        sub(/[^#].*/, "", line)   # 只保留开头的 #
        lvl = length(line)
        if (found && lvl <= level) { exit }
        if (!found) {
          if (index($0, kw) > 0) { found = 1; level = lvl }
          next
        }
        print
        next
      }
      if (found) print
    }
  ' "$file"
}

heading_exists() {
  local file="$1" kw="$2"
  grep -qE "^#+.*${kw}" "$file"
}

# ---------------------------------------------------------------------------
# 检查 1：7 个必填段落齐全
# ---------------------------------------------------------------------------
info ""
info "-- 必填段落 --"

declare -a SECTIONS=("范围内" "范围外" "假设与依赖" "验收标准" "里程碑" "双方职责" "变更流程")
declare -A SECTION_OK

for kw in "${SECTIONS[@]}"; do
  if heading_exists "$TARGET" "$kw"; then
    ok "包含段落标题：${kw}"
    SECTION_OK["$kw"]=1
  else
    bad "缺少必填段落标题：${kw}（请用 Markdown 标题语法，如 \"## ${kw}\"，标题文字里包含这几个字即可）"
    SECTION_OK["$kw"]=0
  fi
done

# ---------------------------------------------------------------------------
# 检查 2：验收标准段落包含量化指标
# ---------------------------------------------------------------------------
info ""
info "-- 验收标准量化 --"

if [[ "${SECTION_OK["验收标准"]:-0}" -eq 1 ]]; then
  acceptance_body="$(extract_section "$TARGET" "验收标准")"
  # 数字 + 单位/百分号，覆盖常见验收指标写法
  if printf '%s' "$acceptance_body" | grep -qE '[0-9０-９]+(\.[0-9]+)?[[:space:]]*(%|％|小时|分钟|秒|天|周|月|次|条|个|份|人|万|元|倍|工作日)'; then
    ok "验收标准段落里检测到量化指标（数字 + 单位/百分比）"
  else
    bad "验收标准段落里没有检测到量化指标——检查是否只写了\"提升效率\"\"让系统更智能\"这类不可验收的表述（参考第 5 章 5.4 节反例/正例表）"
  fi
else
  bad "验收标准段落缺失，无法检查量化指标"
fi

# ---------------------------------------------------------------------------
# 检查 3：范围外至少 2 条
# ---------------------------------------------------------------------------
info ""
info "-- 范围外条款数量 --"

if [[ "${SECTION_OK["范围外"]:-0}" -eq 1 ]]; then
  scope_out_body="$(extract_section "$TARGET" "范围外")"
  bullet_count="$(printf '%s\n' "$scope_out_body" | grep -cE '^[[:space:]]*([-*•]|[0-9]+[.、)])')"
  if [[ "$bullet_count" -ge 2 ]]; then
    ok "范围外段落检测到 ${bullet_count} 条列表项（要求至少 2 条）"
  else
    bad "范围外段落只检测到 ${bullet_count} 条列表项，要求至少 2 条——用 \"- \" 或 \"1. \" 之类的列表语法逐条列出，不要写成一段话"
  fi
else
  bad "范围外段落缺失，无法检查条款数量"
fi

# ---------------------------------------------------------------------------
# 检查 4：至少识别出 1 个"权限拿不到"的风险（全文范围检索，不限定在某一段落）
# ---------------------------------------------------------------------------
info ""
info "-- 权限风险识别 --"

perm_hits="$(grep -nE '权限|审批|授权|访问权' "$TARGET" | grep -cE '无法|不能|拿不到|未获|尚未|待批|待审|卡住|风险|阻塞|拒绝|延迟|暂缓|走不通')"
if [[ "$perm_hits" -ge 1 ]]; then
  ok "全文检测到至少 1 处\"权限/审批\" + \"无法/待批/风险\"类表述（${perm_hits} 处）"
else
  bad "全文没有检测到\"权限拿不到\"类的风险表述——材料包 03-系统清单.md 里埋了一个明确的权限风险（MES 数据访问），检查是否已经写进假设与依赖或范围外段落"
fi

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
info ""
info "=== 结果：${PASS}/$((PASS+FAIL)) 项检查通过 ==="
info ""
info "提醒：以上全部是结构性检查。verify.sh 通过不代表你的判断是对的——"
info "请打开 reference-answer.md，对照里面埋的坑和判断标准，逐条自评内容质量。"

if [[ "$FAIL" -eq 0 ]]; then
  exit 0
else
  exit 1
fi
