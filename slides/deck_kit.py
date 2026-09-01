#!/usr/bin/env python3
"""五天课程课件的版式原语。

视觉沿用 build/build_deck.py：冷调纸白底、墨色正文、青色表示已实测、
琥珀表示存疑，所有数字用等宽字体。那个文件是跑通的，不动它，这里另起一份。

和内容导览版的两处差别：
  1. 多了 example()——课件相对教材的唯一增量是“每条理论配一个例子”，
     例子需要一个固定的、和正文行明显区分的容器，还要挂来源标签。
  2. 多了 section() 与 agenda()——课要分模块，学员得随时知道走到哪了。
"""
from pptx import Presentation
from pptx.util import Inches as In, Pt
from pptx.dml.color import RGBColor
from lxml import etree

import figures

GROUND = RGBColor(0xF3, 0xF5, 0xF2)   # 纸白底
PANEL  = RGBColor(0xFF, 0xFF, 0xFF)   # 卡片、封面
INK    = RGBColor(0x14, 0x1C, 0x24)   # 标题
INK2   = RGBColor(0x38, 0x49, 0x5A)   # 正文
MUTED  = RGBColor(0x6B, 0x7E, 0x8F)   # 辅助
RULE   = RGBColor(0xD6, 0xDD, 0xD8)   # 分隔线
VERIFY = RGBColor(0x0B, 0x8E, 0x77)   # 青：已实测 / 正确做法
CAVEAT = RGBColor(0xB2, 0x6E, 0x10)   # 琥珀：存疑 / 危险
WRONG  = RGBColor(0xA8, 0x3A, 0x32)   # 砖红：错误做法
EXBG   = RGBColor(0xF7, 0xF9, 0xF6)   # 例子卡底

CN = "微软雅黑"      # 中文：Windows / WPS 通用，不挑机器
MONO = "Consolas"   # 数字与代码

W, H = 13.333, 7.5
ML = 0.95           # 左边距
CW = 11.4           # 正文可用宽度


def set_cjk(run, cn=CN):
    """python-pptx 只写 latin 字体，中文会走回退。手动补 eastAsia。"""
    rPr = run._r.get_or_add_rPr()
    ns = '{http://schemas.openxmlformats.org/drawingml/2006/main}ea'
    ea = rPr.find(ns)
    if ea is None:
        ea = etree.SubElement(rPr, ns)
    ea.set('typeface', cn)


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = In(W), In(H)

    def slide(self, bg=GROUND, bar=VERIFY):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = bg
        if bar is not None:
            r = s.shapes.add_shape(1, In(0), In(0), In(0.055), In(H))
            r.fill.solid(); r.fill.fore_color.rgb = bar
            r.line.fill.background(); r.shadow.inherit = False
        return s

    def save(self, path):
        self.prs.save(path)
        return len(self.prs.slides._sldIdLst)


# ────────────────────────── 文本基元 ──────────────────────────

def tb(s, x, y, w, h):
    box = s.shapes.add_textbox(In(x), In(y), In(w), In(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def line(tf, text, size, color=INK, bold=False, mono=False,
         space_after=0, space_before=0, first=False, spacing=1.0):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(space_after); p.space_before = Pt(space_before)
    p.line_spacing = spacing
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = MONO if mono else CN
    set_cjk(r, MONO if mono else CN)
    return p


def rich(tf, parts, size=15, color=INK2, first=False, spacing=1.45,
         space_before=0, space_after=0):
    """一行里混排多种样式。parts 为 (文本, 覆盖项) 列表。

    覆盖项可含 color / bold / mono / size，缺省沿用整行设置。
    用于“正确做法用青色、错误做法用砖红”这类行内强调。
    """
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.line_spacing = spacing
    p.space_before = Pt(space_before); p.space_after = Pt(space_after)
    for text, ov in parts:
        r = p.add_run(); r.text = text
        r.font.size = Pt(ov.get('size', size))
        r.font.bold = ov.get('bold', False)
        r.font.color.rgb = ov.get('color', color)
        mono = ov.get('mono', False)
        r.font.name = MONO if mono else CN
        set_cjk(r, MONO if mono else CN)
    return p


def rule(s, y, x=ML, w=CW, color=RULE, thick=0.012):
    ln = s.shapes.add_shape(1, In(x), In(y), In(w), In(thick))
    ln.fill.solid(); ln.fill.fore_color.rgb = color
    ln.line.fill.background(); ln.shadow.inherit = False
    return ln


# ────────────────────────── 页面构件 ──────────────────────────

def eyebrow(s, num, label, right=None):
    """页眉：左侧模块编号 + 标签，右侧可放当天/关卡定位。"""
    tf = tb(s, ML, 0.55, 9, 0.35)
    p = tf.paragraphs[0]
    if num:
        r = p.add_run(); r.text = str(num) + "   "
        r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = VERIFY
        r.font.name = MONO; set_cjk(r, MONO)
    r = p.add_run(); r.text = label
    r.font.size = Pt(12); r.font.color.rgb = MUTED
    r.font.name = CN; set_cjk(r)
    if right:
        tf2 = tb(s, W - 4.6, 0.55, 3.65, 0.35)
        p2 = tf2.paragraphs[0]
        p2.alignment = 2  # 右对齐
        r = p2.add_run(); r.text = right
        r.font.size = Pt(11); r.font.color.rgb = MUTED
        r.font.name = CN; set_cjk(r)


def heading(s, text, y=1.05, size=32, w=None, color=INK):
    tf = tb(s, ML, y, w or CW, 1.5)
    line(tf, text, size, color, bold=True, first=True, spacing=1.16)
    return tf


def body(s, text, y, size=15.5, color=INK2, w=None, spacing=1.5, x=None):
    tf = tb(s, x if x is not None else ML, y, w or 10.9, 1.4)
    line(tf, text, size, color, first=True, spacing=spacing)
    return tf


def bignum(s, x, y, value, unit=None, color=VERIFY, nsize=48, w=3.2):
    tf = tb(s, x, y, w, 1.0)
    line(tf, value, nsize, color, bold=True, mono=True, first=True, spacing=1.0)
    if unit:
        line(tf, unit, 12, MUTED, space_before=4, spacing=1.3)
    return tf


def card(s, x, y, w, h, kicker=None, title=None, text=None,
         accent=None, bg=PANEL, tsize=15, bsize=12.5):
    box = s.shapes.add_shape(1, In(x), In(y), In(w), In(h))
    box.fill.solid(); box.fill.fore_color.rgb = bg
    box.line.color.rgb = accent or RULE
    box.line.width = Pt(1); box.shadow.inherit = False
    tf = tb(s, x + 0.24, y + 0.20, w - 0.48, h - 0.38)
    first = True
    if kicker:
        line(tf, kicker, 10.5, accent or MUTED, bold=True, first=True, space_after=5)
        first = False
    if title:
        line(tf, title, tsize, INK, bold=True, first=first, space_after=5, spacing=1.25)
        first = False
    if text:
        line(tf, text, bsize, INK2, first=first, spacing=1.42)
    return tf


def example(s, y, text, source, x=ML, w=None, h=1.15, size=13.5, label="例"):
    """例子卡。

    课件相对教材的增量全在这个构件上：每条理论主张下面挂一个它。
    source 是来源标签，必须能回溯到书里——章节号、Lab 编号或原始出处，
    不写来源的例子不许上台。
    """
    w = w or CW
    box = s.shapes.add_shape(1, In(x), In(y), In(w), In(h))
    box.fill.solid(); box.fill.fore_color.rgb = EXBG
    box.line.fill.background(); box.shadow.inherit = False
    tag = s.shapes.add_shape(1, In(x), In(y), In(0.038), In(h))
    tag.fill.solid(); tag.fill.fore_color.rgb = CAVEAT
    tag.line.fill.background(); tag.shadow.inherit = False

    tf = tb(s, x + 0.26, y + 0.16, w - 0.55, h - 0.3)
    p = tf.paragraphs[0]; p.line_spacing = 1.42
    r = p.add_run(); r.text = label + "　"
    r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = CAVEAT
    r.font.name = CN; set_cjk(r)
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.color.rgb = INK2
    r.font.name = CN; set_cjk(r)
    line(tf, "— " + source, 10.5, MUTED, space_before=5, spacing=1.2)
    return tf


def bullets(s, y, items, x=ML, w=None, size=14.5, gap=8, marker="—",
            color=INK2, spacing=1.42):
    """items 为字符串，或 (前缀, 正文) 二元组；前缀走加粗墨色。"""
    tf = tb(s, x, y, w or CW, 3.0)
    first = True
    for it in items:
        if isinstance(it, tuple):
            head, rest = it
            parts = [(marker + "　", {'color': VERIFY, 'bold': True}),
                     (head, {'color': INK, 'bold': True}),
                     ("　" + rest, {})]
        else:
            parts = [(marker + "　", {'color': VERIFY, 'bold': True}),
                     (it, {})]
        rich(tf, parts, size=size, color=color, first=first,
             spacing=spacing, space_before=0 if first else gap)
        first = False
    return tf


def table(s, x, y, rows, widths, head=True, hl=None, fsize=12.5,
          rowh=0.38, headh=0.32, accent=VERIFY):
    """rows[0] 为表头。hl 为需要高亮的行索引（可为 int 或 int 集合）。"""
    if isinstance(hl, int):
        hl = {hl}
    hl = hl or set()
    cy = y
    for i, row in enumerate(rows):
        cx = x
        is_head = head and i == 0
        for j, cell in enumerate(row):
            tf = tb(s, cx, cy, widths[j], 0.3)
            col = MUTED if is_head else (accent if i in hl else INK2)
            mono = (not is_head) and j > 0 and any(ch.isdigit() for ch in cell)
            line(tf, cell, 10.5 if is_head else fsize, col,
                 bold=is_head or i in hl, mono=mono, first=True, spacing=1.2)
            cx += widths[j]
        cy += headh if is_head else rowh
        rule(s, cy - 0.08, x, sum(widths))
    return cy


def quote(s, y, text, w=10.4, size=14, color=INK2, accent=VERIFY):
    bar = s.shapes.add_shape(1, In(ML), In(y), In(0.045), In(0.78))
    bar.fill.solid(); bar.fill.fore_color.rgb = accent
    bar.line.fill.background(); bar.shadow.inherit = False
    tf = tb(s, ML + 0.28, y + 0.02, w, 0.8)
    line(tf, text, size, color, first=True, spacing=1.45)
    return tf


MAXIM_KIND = {"逐字": VERIFY, "提炼": MUTED, "合成": CAVEAT}


def maxim(s, text, expand=None, kind="逐字", src=None, size=32, y=2.0):
    """本节金句页：整页一句话，带出处标记。

    出处这一栏不是装饰，是硬要求。一句话越好记，越容易被转述成"书里说的"；
    标了出处，听众可以回去查。**查不到的金句是负债。**

    kind 三档，和书里的证据分档同一套规矩：
      逐字  正文原句，可以说"书里原话是"
      提炼  书里有完整论证，这句是为讲台压缩的，不冒充原句
      合成  要两处论证合起来才成立，src 要把两处都列出来
    """
    tf = tb(s, ML, y, CW, 2.3)
    line(tf, text, size, INK, bold=True, first=True, spacing=1.22)
    ry = y + 2.62
    rule(s, ry, ML, 6.4)
    if expand:
        body(s, expand, ry + 0.28, size=15.5, w=10.7)
    if src:
        tf2 = tb(s, ML, 6.62, CW, 0.4)
        rich(tf2, [(kind, {'color': MAXIM_KIND.get(kind, MUTED),
                           'bold': True, 'size': 11}),
                   ("\u3000\u3000", {}), (src, {'color': MUTED, 'size': 11.5})],
             size=11.5, color=MUTED, first=True, spacing=1.3)
    return s


def steps(s, y, items, x=ML, w=None, h=1.55, accent=VERIFY, gap=0.16):
    """横排流程：一串带序号的方块，中间不画箭头，靠间距和序号读出顺序。"""
    w = w or CW
    n = len(items)
    bw = (w - gap * (n - 1)) / n
    for i, it in enumerate(items):
        num, title, text = it if len(it) == 3 else (str(i + 1), it[0], it[1])
        bx = x + i * (bw + gap)
        box = s.shapes.add_shape(1, In(bx), In(y), In(bw), In(h))
        box.fill.solid(); box.fill.fore_color.rgb = PANEL
        box.line.color.rgb = RULE; box.line.width = Pt(1)
        box.shadow.inherit = False
        top = s.shapes.add_shape(1, In(bx), In(y), In(bw), In(0.045))
        top.fill.solid(); top.fill.fore_color.rgb = accent
        top.line.fill.background(); top.shadow.inherit = False
        tf = tb(s, bx + 0.20, y + 0.24, bw - 0.4, h - 0.4)
        line(tf, num, 11, accent, bold=True, mono=True, first=True, space_after=4)
        line(tf, title, 13.5, INK, bold=True, space_after=4, spacing=1.25)
        line(tf, text, 11.5, INK2, spacing=1.36)


def section(s, num, title, sub=None, kicker=None):
    """模块分隔页。整页只有一句话，用来切换节奏。

    编号和 kicker 共用一行——分成两个文本框会互相压，标称高度不是渲染高度。
    """
    tf = tb(s, ML, 2.05, CW, 0.4)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = num
    r.font.size = Pt(14); r.font.bold = True
    r.font.color.rgb = VERIFY; r.font.name = MONO; set_cjk(r, MONO)
    if kicker:
        r = p.add_run(); r.text = "　　" + kicker
        r.font.size = Pt(12.5); r.font.color.rgb = MUTED
        r.font.name = CN; set_cjk(r)
    tf2 = tb(s, ML, 2.62, CW, 1.6)
    line(tf2, title, 42, INK, bold=True, first=True, spacing=1.14)
    rule(s, 4.5, ML, 6.2)
    if sub:
        body(s, sub, 4.8, size=16, w=9.6)


def timetable(s, y, rows, x=ML, w=None):
    """时间表：左列时间走等宽，右列内容。"""
    w = w or CW
    return table(s, x, y, rows, [1.55, 3.5, w - 5.05], fsize=13, rowh=0.42)


def footer(s, text):
    tf = tb(s, ML, H - 0.62, CW, 0.35)
    line(tf, text, 10.5, MUTED, first=True)


def checklist(s, y, items, x=ML, w=None, size=14, gap=9):
    """本节清单：□ 打头，学员能当场在讲义上打勾。"""
    tf = tb(s, x, y, w or CW, 3.0)
    first = True
    for it in items:
        rich(tf, [("□　", {'color': VERIFY, 'bold': True, 'size': size + 1}),
                  (it, {})],
             size=size, color=INK2, first=first, spacing=1.42,
             space_before=0 if first else gap)
        first = False
    return tf


def contrast(s, y, wrong, right, h=2.1, wtitle="不该这么说", rtitle="该这么说"):
    """错／对两栏。课上最有效的一种页面，因为反面比正面好记。"""
    for i, (title, items, col) in enumerate(
            [(wtitle, wrong, WRONG), (rtitle, right, VERIFY)]):
        x = ML + i * 5.85
        box = s.shapes.add_shape(1, In(x), In(y), In(5.55), In(h))
        box.fill.solid(); box.fill.fore_color.rgb = PANEL
        box.line.color.rgb = col; box.line.width = Pt(1)
        box.shadow.inherit = False
        tf = tb(s, x + 0.26, y + 0.2, 5.05, h - 0.4)
        line(tf, title, 11, col, bold=True, first=True, space_after=8)
        for it in items:
            line(tf, "· " + it, 13, INK2, space_after=7, spacing=1.38)


def figure(s, macro, y, h, x=None, w=None, src=None):
    """把 build/figures.tex 里的一张图贴进页面。

    给可用高度和可用宽度，按自然宽高比取较小的缩放倍数，水平居中。
    返回图的底边 y，方便在下面接例子卡。

    **贴之前先用 figures.fit_pt() 算一遍等效字号。** 图里的标签是 8pt，
    缩到幻灯片上不足 10.5pt 就别贴了——那是课件里最小的字号，
    再小投影仪后排看不见。宁可让那一页保持原样，也不要贴一张看不清的图。
    """
    x = ML if x is None else x
    w = CW if w is None else w
    nw, nh = figures.size(macro)
    k = min(w / nw, h / nh)
    fw, fh = nw * k, nh * k
    s.shapes.add_picture(str(figures.path(macro)),
                         In(x + (w - fw) / 2), In(y), In(fw), In(fh))
    if src:
        tf = tb(s, x, y + fh + 0.10, w, 0.3)
        p = tf.paragraphs[0]
        p.alignment = 2
        r = p.add_run(); r.text = "— " + src
        r.font.size = Pt(10.5); r.font.color.rgb = MUTED
        r.font.name = CN; set_cjk(r)
        return y + fh + 0.34
    return y + fh


def figpage(s, macro, title, src, note=None):
    """整页一张图。竖长的图只有这种放法字号才够。

    标题压到一行 20pt，图占掉剩下的全部高度——这一页的用法是讲师翻到这里
    停两分钟，让学员自己在图上找，所以不要再往上堆文字。
    """
    tf = tb(s, ML, 0.98, CW, 0.4)
    line(tf, title, 20, INK, bold=True, first=True, spacing=1.2)
    # 图的底边必须停在页脚上方：页脚落在图里的话，版式核算会把页脚当成
    # “图这个框里的文字”，报一处撑破框——那是误报，但改图比改核算划算。
    figure(s, macro, 1.52, 4.90 if note else 5.23, w=CW + 0.9, x=ML - 0.45)
    if note:
        tfn = tb(s, ML, 6.52, CW, 0.3)
        line(tfn, note, 12, INK2, first=True, spacing=1.3)
    footer(s, src)


def figplate(s, macro, src):
    """整页一张比喻图。

    比喻图自带标题和正文（书里就是这么排的），所以这一页不再加页面标题——
    加了就是同一句话说两遍，还白占掉半英寸，图跟着缩一号。
    """
    figure(s, macro, 1.05, 5.70, w=CW + 0.9, x=ML - 0.45)
    footer(s, src)


def picture(s, name, y, h, x=None, w=None):
    """把 assets-day1/ 下的一张位图贴进页面，按自然宽高比缩放，水平居中。

    和 figure() 分工不同：figure() 贴的是书里那些 TikZ 图，追求最少的笔画；
    picture() 贴的是 artifacts.py 造的**示例产物**，追求像真东西——
    表格要填满、对话要有具体的错、数字要能一路算下去。
    课件上这两种图不能互相替代。
    """
    from PIL import Image
    import pathlib as _p
    path = _p.Path(__file__).resolve().parent / "assets-slides" / name
    nw, nh = Image.open(path).size
    x = ML - 0.45 if x is None else x
    w = CW + 0.9 if w is None else w
    k = min(w / nw, h / nh)
    fw, fh = nw * k, nh * k
    px = x + (w - fw) / 2
    fr = s.shapes.add_shape(1, In(px - 0.025), In(y - 0.025),
                            In(fw + 0.05), In(fh + 0.05))
    fr.fill.solid(); fr.fill.fore_color.rgb = RULE
    fr.line.fill.background(); fr.shadow.inherit = False
    s.shapes.add_picture(str(path), In(px), In(y), In(fw), In(fh))
    return y + fh


def picpage(s, name, title, src, note=None):
    """整页一张示例产物图。

    版式跟 figpage 一致：标题压到一行 20pt，图占掉剩下的高度。
    这一页的用法也一样——讲师翻到这里停两分钟，让学员自己在图上找，
    所以不要再往上堆文字。
    """
    tf = tb(s, ML, 0.98, CW, 0.4)
    line(tf, title, 20, INK, bold=True, first=True, spacing=1.2)
    picture(s, name, 1.52, 4.62 if note else 4.95)
    if note:
        tfn = tb(s, ML, 6.34, CW, 0.3)
        line(tfn, note, 12, INK2, first=True, spacing=1.3)
    footer(s, src)


def qa(s, y, q, a, size=14.5):
    """自检问题：一问一答，答案压在下面，讲师先问后翻。"""
    tf = tb(s, ML, y, CW, 0.6)
    rich(tf, [("问　", {'color': CAVEAT, 'bold': True, 'size': 12}),
              (q, {'color': INK, 'bold': True, 'size': size + 1})],
         first=True, spacing=1.4)
    tf2 = tb(s, ML, y + 0.72, CW, 1.2)
    rich(tf2, [("答　", {'color': VERIFY, 'bold': True, 'size': 12}),
               (a, {})], size=size, first=True, spacing=1.45)
    return tf2
