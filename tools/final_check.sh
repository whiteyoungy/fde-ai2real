#!/bin/bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
set -euo pipefail
# 15 章文风重排的最终复核
cd "$(dirname "$0")/.."
B="${FDE_PROSE_BASELINE:-}"
# prose_check.py 判定「需人工确认」时以 1 退出。命令替换里不兜住的话，
# set -e 会让整个脚本停在第一个有改动的章，后面的章根本没跑——
# 而输出看起来像「前面几章都通过了」，最危险的一种假通过。
# 路径随 2026-09 改版重排过一次：上册章号 04→10、05→11、11→16、12→17、13→18；
# 下册 04→06、05→04、07→09、08→10、09→08、10→12、11→13；
# 原下册 16、17 章已抽成别册三。改章号时这份清单要跟着改，否则这道检查会静默跳过。
FILES=(vol1/10-第1关选题.md vol1/11-第2关定界.md vol1/16-甲乙方关系与商务链路.md vol1/17-国企银行政务交付.md
       vol1/18-合规与备案.md vol2/01-生产级工程基线.md vol2/06-企业集成与协议桥接.md
       vol2/04-数据管道与向量层.md vol2/09-GenAI系统与Agent编排.md vol2/10-部署护栏与可观测性.md
       vol2/08-评估的工程实现.md vol2/12-国产模型与平台栈.md vol2/13-信创改造与国产化适配.md
       booklet-career/01-90天上岗计划.md booklet-career/02-面试与作品集.md)
fail=0
for f in "${FILES[@]}"; do
  bn=$(basename "$f")
  if [ -n "$B" ] && [ -f "$B/$bn" ]; then
    out=$(python3 tools/prose_check.py "$f" --vs "$B/$bn" 2>&1 || true)
  elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    out=$(python3 tools/prose_check.py "$f" --vs HEAD 2>&1 || true)
  else
    out=$(python3 tools/prose_check.py "$f" 2>&1 || true)
  fi
  m=$(echo "$out" | grep -o '>60字 *[0-9.]*%' | head -1)
  q=$(echo "$out" | grep -o '引号配对 [^ ]*')
  if echo "$out" | grep -q '结论：'; then
    c=$(echo "$out" | tail -1 | sed 's/  结论：//')
  else
    c="通过（无内容基线，仅检查文风）"
  fi
  # || true 不能省：set -e ＋ pipefail 下，grep 无匹配（＝全部没变，正是想要的结果）
  # 会让整个脚本以 1 退出，看起来像检查失败。
  bad=$(echo "$out" | grep '\*\*变了\*\*' | awk '{print $1}' | tr '\n' ',' || true)
  printf '%-34s %-14s %-12s %s %s\n' "${f}" "$m" "$q" "$c" "$bad"
  # 不在这里中断：需人工确认的章要全部打印出来，最后统一给结论。
  # 中途 exit 会让后面的章根本没被检查，而看起来像「前面都过了」。
  echo "$c" | grep -q 通过 || fail=1
  true
done
echo; echo "指纹复核：$([ $fail -eq 0 ] && echo 全部通过 || echo '有章需人工确认')"
