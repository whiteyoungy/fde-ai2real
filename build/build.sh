#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# 分册构建。用法：
#   ./build/build.sh          全部构建（上册、下册、两本别册）
#   ./build/build.sh vol1     只构建上册
#   ./build/build.sh vol2     只构建下册
#   ./build/build.sh codex    只构建别册一（用 Codex 做 FDE 项目）
#   ./build/build.sh dsh      只构建别册二（用 DeepSeek Harness 做 FDE 项目）
#   ./build/build.sh career   只构建别册三（90 天上岗与求职）
#
# 三本别册都独立成书，不进上下册的目录，只被上下册单向引用。
set -euo pipefail
cd "$(dirname "$0")/.."

build_one() {
  local vol="$1" name="$2"
  local out="build/${name}.pdf"
  local chapters
  # 排序必须用 LC_ALL=C（按字节），不能用环境 locale。
  # en_US.UTF-8 的排序规则会忽略标点：「06a-最小本体」里的 a 会排到
  # 「06-第3关切片」的「第」前面，章节顺序就错了。字节序下 - (0x2D) < a (0x61)，才对。
  chapters=$(ls "${vol}"/*.md | LC_ALL=C sort)

  echo "════════ 构建 ${name} ════════"
  for f in $chapters; do echo "  - $f"; done

  # Mermaid 预处理：把 ```mermaid 代码块转换为 SVG 并替换为图片引用。
  # 若 mmdc（@mermaid-js/mermaid-cli）不可用，脚本会打印警告并降级为
  # 保留代码块原样渲染，不中断构建。
  echo "预处理 Mermaid 图表..."
  local processed
  processed=$(python3 build/preprocess_mermaid.py $chapters)

  local log="build/.tmp/pandoc-${vol}.log"
  mkdir -p build/.tmp

  pandoc $processed \
    --metadata-file="build/metadata-${vol}.yaml" \
    --template=build/template.tex \
    --resource-path=".:${vol}:assets:build/.tmp" \
    --pdf-engine=xelatex \
    --highlight-style=tango \
    --top-level-division=chapter \
    -o "$out" 2> >(tee "$log" >&2)

  echo "已生成 $out"
  pdfinfo "$out" | grep -E '^(Pages|File size)'

  # 缺字检查。xelatex 遇到字体不含的字符时只发 warning 不报错，
  # 字符会静默消失在 PDF 里——⚠（合成案例警示标记）就这样丢过一次。
  # 这些警告淹没在编译噪音中，必须单独汇总出来。
  echo
  local missing
  missing=$(grep -oP 'Missing character: There is no \K\S+' "$log" 2>/dev/null | sort -u || true)
  if [ -n "$missing" ]; then
    echo "⚠️  ${name} 检测到缺字（这些字符不会出现在 PDF 里）："
    echo "$missing" | sed 's/^/    /'
    echo
    echo "    修法：在 build/metadata-${vol}.yaml 的 header-includes 里"
    echo "    把该字符所在的 Unicode 区段加进 \\xeCJKDeclareCharClass{CJK}。"
    return 1
  fi
  echo "✅ ${name} 缺字检查通过"
  echo
}

TARGET="${1:-all}"
case "$TARGET" in
  vol1) build_one vol1 "FDE-把AI交付到真实世界-上册-方法与决策" ;;
  vol2) build_one vol2 "FDE-把AI交付到真实世界-下册-工程与系统" ;;
  # 别册独立成书：内容不进上下册的目录，正文里只从上下册单向引用过去。
  # 目录名带连字符，metadata 文件名跟着叫 metadata-booklet-codex.yaml。
  codex) build_one booklet-codex "FDE-把AI交付到真实世界-别册一-用Codex做FDE项目" ;;
  dsh) build_one booklet-dsh "FDE-把AI交付到真实世界-别册二-用DeepSeekHarness做FDE项目" ;;
  # 别册三：原下册第 16、17 章。抽出来的判据是「谁可以整章跳过、跳过之后缺什么」——
  # 已经在岗的读者整本跳过，正文判据链条一环不缺，所以它不该占正文的位置。
  career) build_one booklet-career "FDE-把AI交付到真实世界-别册三-90天上岗与求职" ;;
  all)
    build_one vol1 "FDE-把AI交付到真实世界-上册-方法与决策"
    build_one vol2 "FDE-把AI交付到真实世界-下册-工程与系统"
    build_one booklet-codex "FDE-把AI交付到真实世界-别册一-用Codex做FDE项目"
    build_one booklet-dsh "FDE-把AI交付到真实世界-别册二-用DeepSeekHarness做FDE项目"
    build_one booklet-career "FDE-把AI交付到真实世界-别册三-90天上岗与求职"
    ;;
  *) echo "用法：$0 [vol1|vol2|codex|dsh|career|all]" >&2; exit 2 ;;
esac
