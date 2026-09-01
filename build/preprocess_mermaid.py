#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""
Mermaid 预处理脚本。

用途：pandoc 原生不渲染 Mermaid 代码块。本脚本扫描传入的 Markdown 文件，
把 ```mermaid ... ``` 代码块渲染为 SVG（依赖 mmdc / @mermaid-js/mermaid-cli），
并把代码块替换为图片引用，写入 build/.tmp/ 下的同名文件供 pandoc 消费。

降级策略：如果 mmdc 不可用（未安装，或调用失败），则该 mermaid 代码块保持
原样（作为普通代码块渲染进 PDF），并打印警告，不中断整体构建。

用法：
    python3 build/preprocess_mermaid.py book/00-导读.md [book/xx.md ...]

输出：
    每处理完一个文件，在 stdout 打印一行处理后文件的路径（供 build.sh 收集），
    其余日志信息打印到 stderr，避免污染 stdout 的文件列表。
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = REPO_ROOT / "build" / ".tmp"
SVG_DIR = REPO_ROOT / "assets" / "mermaid"

MERMAID_BLOCK_RE = re.compile(
    r"```mermaid[ \t]*\n(.*?)\n```",
    re.DOTALL,
)

PUPPETEER_CONFIG = TMP_DIR / "puppeteer-config.json"
PUPPETEER_CONFIG_CONTENT = (
    '{"args":["--no-sandbox","--disable-setuid-sandbox"]}\n'
)

# Mermaid 配置。htmlLabels: false 是关键——
# mermaid 默认把标签包在 <foreignObject> 里（即 SVG 里嵌 HTML），
# 而 SVG→PDF 的转换器基本都不支持 foreignObject，会直接渲染成空白。
# 表现就是「图的框线都在、中文全没了」。关掉它，mermaid 会输出
# 真正的 <text> 元素，中文才进得了 PDF。
MERMAID_CONFIG = TMP_DIR / "mermaid-config.json"
MERMAID_CONFIG_CONTENT = """{
  "htmlLabels": false,
  "flowchart":  {"htmlLabels": false, "useMaxWidth": true},
  "sequence":   {"useMaxWidth": true},
  "gantt":      {"useMaxWidth": true},
  "themeVariables": {"fontFamily": "Noto Sans CJK SC, Noto Sans CJK, sans-serif"}
}
"""


def mmdc_available() -> bool:
    return shutil.which("mmdc") is not None


def rsvg_convert_available() -> bool:
    return shutil.which("rsvg-convert") is not None


def render_svg(mmd_source: str, svg_path: Path) -> bool:
    """调用 mmdc 把 mermaid 源码渲染为 SVG。成功返回 True。"""
    mmd_path = svg_path.with_suffix(".mmd")
    mmd_path.write_text(mmd_source, encoding="utf-8")
    try:
        result = subprocess.run(
            [
                "mmdc",
                "-i", str(mmd_path),
                "-o", str(svg_path),
                "-p", str(PUPPETEER_CONFIG),
                "-c", str(MERMAID_CONFIG),
                "-b", "white",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[mermaid] 调用 mmdc 失败：{exc}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(f"[mermaid] mmdc 渲染失败（{svg_path.name}）：{result.stderr.strip()}", file=sys.stderr)
        return False
    return svg_path.exists()


def process_file(md_path: Path, use_mmdc: bool) -> Path:
    text = md_path.read_text(encoding="utf-8")
    stem = md_path.stem
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        mmd_source = match.group(1)

        if not use_mmdc:
            print(
                f"[mermaid] 警告：mmdc 不可用，{md_path.name} 中第 {counter} 个 "
                f"mermaid 代码块将以源码形式渲染进 PDF。",
                file=sys.stderr,
            )
            return match.group(0)

        svg_name = f"{stem}-{counter}.svg"
        svg_path = SVG_DIR / svg_name
        ok = render_svg(mmd_source, svg_path)
        if not ok:
            print(
                f"[mermaid] 警告：{md_path.name} 第 {counter} 个 mermaid 代码块转换失败，"
                f"降级为源码渲染。",
                file=sys.stderr,
            )
            return match.group(0)

        rel_path = f"assets/mermaid/{svg_name}"
        print(f"[mermaid] {md_path.name} 第 {counter} 个 mermaid 块 -> {rel_path}", file=sys.stderr)
        return f"![]({rel_path})"

    new_text = MERMAID_BLOCK_RE.sub(replace, text)

    # 剥掉 emoji 变体选择符 U+FE0F。它在印刷品里没有意义，但会让 xelatex 报缺字，
    # 而在 LaTeX 层用 \newunicodechar{...}{} 给它一个空替换会和 microtype 冲突
    # （Argument of \MT@is@char has an extra }），所以在这里直接去掉。
    new_text = new_text.replace("️", "")

    out_path = TMP_DIR / md_path.name
    out_path.write_text(new_text, encoding="utf-8")
    return out_path


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: preprocess_mermaid.py <markdown files...>", file=sys.stderr)
        return 1

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    PUPPETEER_CONFIG.write_text(PUPPETEER_CONFIG_CONTENT, encoding="utf-8")
    MERMAID_CONFIG.write_text(MERMAID_CONFIG_CONTENT, encoding="utf-8")

    use_mmdc = mmdc_available()
    if use_mmdc:
        # 进一步检测 rsvg-convert，它是将 SVG 嵌入 PDF 的必需工具
        if not rsvg_convert_available():
            print(
                "[mermaid] 警告：检测到 mmdc，但未检测到 rsvg-convert（来自 librsvg2-bin）。"
                "为避免 xelatex 报晦涩错误，已自动降级为源码渲染路径。"
                "如需 Mermaid 图形渲染，请安装 librsvg2-bin：例如 apt-get install librsvg2-bin。",
                file=sys.stderr,
            )
            use_mmdc = False
        else:
            print("[mermaid] 检测到 mmdc 和 rsvg-convert，使用真实转换路径（mermaid -> SVG）。", file=sys.stderr)
    else:
        print(
            "[mermaid] 警告：未检测到 mmdc（@mermaid-js/mermaid-cli），"
            "降级为源码渲染路径，所有 mermaid 代码块将以纯文本代码块形式出现在 PDF 中。",
            file=sys.stderr,
        )

    for arg in argv:
        md_path = Path(arg).resolve()
        out_path = process_file(md_path, use_mmdc)
        print(str(out_path.relative_to(REPO_ROOT)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
