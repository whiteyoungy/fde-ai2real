#!/usr/bin/env python3
r"""把 build/figures.tex 里的插图渲染成 PNG，供 dayN.py 贴进课件。

书里的插图是 TikZ 画的，课件是 python-pptx 生成的，两边不通。这个模块
把中间那段接上：一次 xelatex 跑完当天要用的全部插图，standalone 类
逐图裁边成单独一页，再 pdftoppm 转成 PNG。

三件事值得先说清楚：

1. **不是所有图都能贴。** 图里的标签是 8pt（\scriptsize），贴进 13.33 英寸
   宽的幻灯片之后，等效字号 ＝ 8 × 缩放倍数。课件最小的字是 10.5pt，
   低于它投影仪后排看不见。所以竖长的图（宽高比 < 1.2）只能整页放，
   再窄的干脆不贴——`fit_pt()` 把这个换算摆出来，选图时先算一遍。

2. **缓存按 figures.tex 的内容哈希。** 改了图重跑构建会自动重渲染，
   改的是别的图也一起重渲染——反正一次 xelatex 跑完全部，不值得做细粒度。

3. **渲染失败不静默。** 缺 xelatex 或某个宏名写错，直接抛异常让构建停下来，
   不要生成一份少了图的 pptx——那种 pptx 看起来是好的。
"""
import hashlib
import pathlib
import shutil
import struct
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
FIGTEX = ROOT / "build" / "figures.tex"
CACHE = HERE / ".figcache"
DPI = 400

_PREAMBLE = r"""\documentclass[border=3pt,multi=tikzpicture]{standalone}
\usepackage{xeCJK}
\setCJKmainfont{Noto Serif CJK SC}
\setCJKsansfont{Noto Sans CJK SC}
\setCJKmonofont{Noto Sans Mono CJK SC}
\usepackage{tikz}
\usepackage{xcolor}
\usepackage{adjustbox}
\xeCJKDeclareCharClass{CJK}{
  "00D7, "0370 -> "03FF, "2010 -> "206F, "2190 -> "21FF,
  "2200 -> "22FF, "2460 -> "24FF, "2500 -> "257F,
  "25A0 -> "25FF, "2600 -> "26FF, "2700 -> "27BF
}
\input{build/figures.tex}
\begin{document}
"""


def _stamp():
    return hashlib.sha1(FIGTEX.read_bytes()).hexdigest()[:10]


def _png_size_in(path):
    """从 PNG 头里读像素尺寸，再按渲染 DPI 换算成英寸。不引入 PIL。"""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG：%s" % path)
    w, h = struct.unpack(">II", head[16:24])
    return w / float(DPI), h / float(DPI)


_sizes = {}


def render(macros):
    """渲染一批插图，返回 {宏名: PNG 路径}。已缓存的跳过。"""
    macros = list(dict.fromkeys(macros))
    if not macros:
        return {}
    tag = _stamp()
    CACHE.mkdir(exist_ok=True)
    out = {m: CACHE / ("%s-%s.png" % (m, tag)) for m in macros}
    todo = [m for m in macros if not out[m].exists()]

    if todo:
        if not shutil.which("xelatex") or not shutil.which("pdftoppm"):
            raise RuntimeError("渲染插图需要 xelatex 和 pdftoppm，本机没找到")
        work = CACHE / ".build"
        work.mkdir(exist_ok=True)
        tex = work / "figs.tex"
        tex.write_text(_PREAMBLE + "\n".join("\\%s" % m for m in todo)
                       + "\n\\end{document}\n", encoding="utf-8")
        # cwd 必须是仓库根，figures.tex 里的 \input 路径是相对根写的
        r = subprocess.run(["xelatex", "-interaction=nonstopmode",
                            "-output-directory=" + str(work), str(tex)],
                           cwd=str(ROOT), capture_output=True, text=True)
        pdf = work / "figs.pdf"
        if not pdf.exists():
            raise RuntimeError("xelatex 没生成 PDF：\n" + r.stdout[-2000:])
        subprocess.run(["pdftoppm", "-png", "-r", str(DPI), str(pdf),
                        str(work / "p")], check=True)
        pages = sorted(work.glob("p-*.png"))
        if len(pages) != len(todo):
            raise RuntimeError("插图页数对不上：要 %d 张，出来 %d 张。"
                               "多半是某个宏名写错了" % (len(todo), len(pages)))
        for m, p in zip(todo, pages):
            shutil.move(str(p), str(out[m]))
        shutil.rmtree(work, ignore_errors=True)

    for m, p in out.items():
        _sizes[m] = _png_size_in(p)
    return out


def size(macro):
    """插图的自然尺寸（英寸）。render() 之后才有。"""
    return _sizes[macro]


def fit_pt(macro, box_w, box_h):
    """把图放进 box_w × box_h 之后，图里 8pt 的标签等效多大。

    课件正文 15.5pt、表格 12.5pt、例子来源 10.5pt。10.5 是投影仪的底线，
    算出来低于它就别贴了——换整页放，或者按幻灯片重画。
    """
    w, h = _sizes[macro]
    return 8.0 * min(box_w / w, box_h / h)


def path(macro):
    """插图 PNG 的路径。render() 之后才有。"""
    if macro not in _sizes:
        raise KeyError("插图 %s 还没渲染。在 dayN.py 顶上的 FIGS 列表里加上它" % macro)
    return CACHE / ("%s-%s.png" % (macro, _stamp()))
