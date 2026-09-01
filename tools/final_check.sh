#!/bin/bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
set -euo pipefail
# 15 章文风重排的最终复核
cd "$(dirname "$0")/.."
B="${FDE_PROSE_BASELINE:-}"
FILES=(vol1/04-第1关选题.md vol1/05-第2关定界.md vol1/11-甲乙方关系与商务链路.md vol1/12-国企银行政务交付.md
       vol1/13-合规与备案.md vol2/01-生产级工程基线.md vol2/04-企业集成与协议桥接.md
       vol2/05-数据管道与向量层.md vol2/07-GenAI系统与Agent编排.md vol2/08-部署护栏与可观测性.md
       vol2/09-评估的工程实现.md vol2/10-国产模型与平台栈.md vol2/11-信创改造与国产化适配.md
       vol2/16-90天上岗计划.md vol2/17-面试与作品集.md)
fail=0
for f in "${FILES[@]}"; do
  bn=$(basename "$f")
  if [ -n "$B" ] && [ -f "$B/$bn" ]; then
    out=$(python3 tools/prose_check.py "$f" --vs "$B/$bn" 2>&1)
  elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    out=$(python3 tools/prose_check.py "$f" --vs HEAD 2>&1)
  else
    out=$(python3 tools/prose_check.py "$f" 2>&1)
  fi
  m=$(echo "$out" | grep -o '>60字 *[0-9.]*%' | head -1)
  q=$(echo "$out" | grep -o '引号配对 [^ ]*')
  if echo "$out" | grep -q '结论：'; then
    c=$(echo "$out" | tail -1 | sed 's/  结论：//')
  else
    c="通过（无内容基线，仅检查文风）"
  fi
  bad=$(echo "$out" | grep '\*\*变了\*\*' | awk '{print $1}' | tr '\n' ',')
  printf '%-34s %-14s %-12s %s %s\n' "${f}" "$m" "$q" "$c" "$bad"
  echo "$c" | grep -q 通过 || fail=1
done
echo; echo "指纹复核：$([ $fail -eq 0 ] && echo 全部通过 || echo '有章需人工确认')"
