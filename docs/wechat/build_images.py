#!/usr/bin/env python3
"""生成公众号系列文章的配图。

SVG 手写后用 rsvg-convert 转 PNG——中文靠 <text> 元素渲染，
不要用 <foreignObject>（转换器不支持，中文会整片消失）。

配色沿用全项目那套：纸白底、墨色字、青色表示实测结论、琥珀表示风险。
首图一律 900×383（公众号 2.35:1），正文图宽 1080（手机端清晰）。
"""
import pathlib
import subprocess

OUT = pathlib.Path(__file__).parent / "assets"
OUT.mkdir(exist_ok=True)

BG, INK, INK2 = "#F3F5F2", "#141C24", "#38495A"
MUTED, RULE = "#6B7E8F", "#D6DDD8"
VERIFY, CAVEAT, PANEL = "#0B8E77", "#B26E10", "#FFFFFF"
F = "Noto Sans CJK SC, Microsoft YaHei, sans-serif"
M = "DejaVu Sans Mono, Consolas, monospace"


def t(x, y, s, size=16, fill=INK, weight="400", font=F, anchor="start", ls="0"):
    s = (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" '
            f'letter-spacing="{ls}">{s}</text>')


def rect(x, y, w, h, fill, stroke=None, sw=1, rx=3):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{st}/>'


def line(x1, y1, x2, y2, c=RULE, w=1):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{w}"/>'


def render(name, w, h, body, bg=BG):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}">{rect(0,0,w,h,bg,rx=0)}{body}</svg>')
    sp = OUT / f"{name}.svg"
    sp.write_text(svg, encoding="utf-8")
    subprocess.run(["rsvg-convert", "-f", "png", "-w", str(w * 2),
                    "-o", str(OUT / f"{name}.png"), str(sp)], check=True)
    sp.unlink()
    print(f"  {name}.png  {w*2}×{h*2}")


# ══════════ 第 1 篇 · 首图 900×383 ══════════
b = [rect(0, 0, 6, 383, VERIFY, rx=0)]
b.append(t(56, 62, "同一份语料，三种做法", 17, MUTED))
rows = [("BM25 单路", "92%", INK, "400"),
        ("纯向量", "90%", CAVEAT, "700"),
        ("RRF 混合", "98%", INK, "400")]
y = 120
for label, val, col, wt in rows:
    b.append(t(56, y, label, 26, col, wt))
    b.append(t(330, y, val, 40, col, "700", M))
    y += 62
b.append(line(56, 320, 470, 320, RULE))
b.append(t(520, 190, "但在语义改写类查询上，", 16, INK2))
b.append(t(520, 216, "混合比纯向量还低。", 16, INK2))
b.append(t(520, 258, "1241 篇中文语料 · 59 条查询 · Recall@5", 13, MUTED))
render("01-cover", 900, 383, "".join(b))

# ══════════ 第 1 篇 · 图1 分类别对比 ══════════
W, H = 1080, 620
b = [t(56, 66, "把查询按类型拆开，结论就变了", 30, INK, "700")]
b.append(t(56, 100, "混合赢在总账，不是赢在每一项", 17, MUTED))

groups = [("语义改写类", "文档写「费用核销时限」，用户问「报销要等多久」",
           [("BM25", "3/8", MUTED), ("纯向量", "8/8", VERIFY), ("混合", "7/8", CAVEAT)], 150),
          ("埋编号类", "「那个对账差异的事件，编号好像是 INC-20777」",
           [("BM25", "40/40", VERIFY), ("纯向量", "34/40", CAVEAT), ("混合", "40/40", VERIFY)], 380)]
for title, sub, items, gy in groups:
    b.append(rect(56, gy, 968, 190, PANEL, RULE))
    b.append(t(84, gy + 42, title, 22, INK, "700"))
    b.append(t(84, gy + 72, sub, 14, MUTED))
    x = 84
    for lab, val, col in items:
        b.append(t(x, gy + 128, lab, 15, MUTED))
        b.append(t(x, gy + 166, val, 34, col, "700", M))
        x += 300
b.append(t(56, 596, "语义改写类里混合 7/8，比纯向量的 8/8 低——融合不是免费的。",
           17, INK2))
render("01-fig1", W, H, "".join(b))

# ══════════ 第 1 篇 · 图2 三种情形 ══════════
W, H = 1080, 560
b = [t(56, 66, "纯向量什么时候才真的失手", 30, INK, "700")]
b.append(t(56, 100, "构造语料之前先量的三种情形", 17, MUTED))
cases = [("120 篇，每篇主题各异", "100%", "混合毫无价值", VERIFY),
         ("40 篇结构相同的维保卡，查询是裸编号", "40/40", "仍然满分", VERIFY),
         ("1200 篇措辞几乎一致，查询里埋着编号", "29/40", "终于失手", CAVEAT)]
y = 150
for desc, val, note, col in cases:
    b.append(rect(56, y, 968, 108, PANEL, CAVEAT if col == CAVEAT else RULE))
    b.append(t(84, y + 46, desc, 19, INK))
    b.append(t(84, y + 78, note, 14, MUTED))
    b.append(t(984, y + 66, val, 36, col, "700", M, anchor="end"))
    y += 128
b.append(t(56, 536, "企业知识库里，第三类文档往往占大头——这才是混合检索成立的真正理由。",
           17, INK2))
render("01-fig2", W, H, "".join(b))

# ══════════ 第 3 篇 · 首图 900×383 ══════════
b = [rect(0, 0, 6, 383, CAVEAT, rx=0)]
b.append(t(450, 52, "同一个系统，左边是演示，右边是上线", 17, MUTED, anchor="middle"))
b.append(line(450, 78, 450, 350, RULE, 1))
# 左：整洁
b.append(t(56, 118, "Demo 里的数据", 15, VERIFY, "700"))
clean = ["报修内容：呼叫器故障", "科室：骨科三病区", "紧急程度：一般",
         "报修内容：水龙头漏水", "科室：消毒供应中心", "紧急程度：一般"]
y = 152
for r in clean:
    b.append(t(56, y, r, 15, INK2, font=M))
    y += 33
# 右：脏
b.append(t(490, 118, "上线后的真实数据", 15, CAVEAT, "700"))
dirty = [("报修内容：坏了", CAVEAT), ("科室：（空）", CAVEAT),
         ("紧急程度：（未填）", MUTED), ("报修内容：3床呼叫器不响", CAVEAT),
         ("科室：骨三", MUTED), ("紧急程度：（未填）", MUTED)]
y = 152
for r, c in dirty:
    b.append(t(490, y, r, 15, c, font=M))
    y += 33
render("03-cover", 900, 383, "".join(b))

# ══════════ 第 3 篇 · 图1 四类风险 ══════════
W, H = 1080, 540
b = [t(56, 66, "一个漂亮的 Demo，只回答了四件事里的一件", 30, INK, "700")]
b.append(t(56, 100, "立项前该验证的四类风险", 17, MUTED))
risks = [("有没有人真的需要它", "价值风险", False),
         ("人会不会用、用不用得明白", "可用性风险", True),
         ("技术上做不做得出来", "可行性风险", False),
         ("算不算得过账", "商业风险", False)]
y = 150
for desc, name, covered in risks:
    col = VERIFY if covered else CAVEAT
    b.append(rect(56, y, 968, 76, PANEL, col if covered else RULE))
    b.append(rect(56, y, 5, 76, col, rx=0))
    b.append(t(92, y + 34, desc, 20, INK if covered else INK2))
    b.append(t(92, y + 60, name, 13, MUTED))
    tag = "Demo 验证了" if covered else "Demo 没有验证"
    b.append(t(984, y + 46, tag, 15, col, "700", anchor="end"))
    y += 88
b.append(t(56, 516, "用假数据搭的原型证明了界面好用，没证明它在你的真实数据上跑得通。",
           17, INK2))
render("03-fig1", W, H, "".join(b))

# ══════════ 第 2 篇 · 首图 900×383 ══════════
# 数轴只画「已知的两个端点」和它们之间的重叠带。
# 两组各自的完整分布没有量全，不画成两根实心条，免得图比数据说得多。
b = [rect(0, 0, 6, 383, CAVEAT, rx=0)]
b.append(t(56, 60, "两组相似度，中间没有空隙", 27, INK, "700"))
b.append(t(56, 92, "10 对同义改写 / 12 对似而不同 · bge-small-zh-v1.5", 14, MUTED))

AX_Y, X0, X1, V0, V1 = 250, 110, 830, 0.60, 1.00


def _px(v):
    return X0 + (v - V0) / (V1 - V0) * (X1 - X0)


lo, hi = _px(0.651), _px(0.954)
b.append(rect(lo, AX_Y - 46, hi - lo, 92, "#F7EDDD", CAVEAT, 1, rx=2))
b.append(line(X0, AX_Y, X1, AX_Y, INK2, 2))
for v in (0.60, 0.70, 0.80, 0.90, 1.00):
    b.append(line(_px(v), AX_Y - 5, _px(v), AX_Y + 5, INK2, 2))
    b.append(t(_px(v), AX_Y + 28, f"{v:.2f}", 13, MUTED, font=M, anchor="middle"))
b.append(t(lo, AX_Y - 58, "0.651", 24, VERIFY, "700", M, anchor="middle"))
b.append(t(lo, AX_Y - 84, "应命中的最低", 14, VERIFY, anchor="middle"))
b.append(t(hi, AX_Y - 58, "0.954", 24, CAVEAT, "700", M, anchor="middle"))
b.append(t(hi, AX_Y - 84, "不该命中的最高", 14, CAVEAT, anchor="middle"))
b.append(t((lo + hi) / 2, AX_Y + 76, "所有可选阈值都落在这一段里 —— 每一个都既漏又错",
           17, INK2, anchor="middle"))
render("02-cover", 900, 383, "".join(b))

# ══════════ 第 2 篇 · 图1 三个阈值都不行 ══════════
W, H = 1080, 600
b = [t(56, 66, "调高阈值，命中率先归零，误命中还在", 30, INK, "700")]
b.append(t(56, 100, "同一份夹具，只改阈值", 17, MUTED))
b.append(t(84, 158, "阈值", 15, MUTED, font=M))
b.append(t(430, 158, "命中率（满分 10）", 15, MUTED))
b.append(t(760, 158, "误命中（共 12 对）", 15, MUTED))
b.append(line(56, 176, 1024, 176, RULE))
y = 200
for thr, hit, bad, last in [("0.85", 7, 4, False), ("0.90", 5, 2, False),
                            ("0.94", 1, 1, True)]:
    if last:
        b.append(rect(56, y, 968, 104, PANEL, CAVEAT, 2))
    b.append(t(84, y + 62, thr, 34, INK if not last else CAVEAT, "700", M))
    # 命中率：10 格
    for i in range(10):
        on = i < hit
        b.append(rect(430 + i * 30, y + 34, 22, 34, VERIFY if on else "#E4E8E3"))
    # 误命中：12 格
    for i in range(12):
        on = i < bad
        b.append(rect(760 + i * 22, y + 34, 16, 34, CAVEAT if on else "#E4E8E3"))
    y += 116
b.append(t(56, 576,
           "0.94 时缓存已经等于关掉了——10 条同义只认出 1 条，误命中还剩一条。",
           17, INK2))
render("02-fig1", W, H, "".join(b))

# ══════════ 第 2 篇 · 图2 三层分工 ══════════
W, H = 1080, 650
b = [t(56, 66, "阈值救不了，就分层", 30, INK, "700")]
b.append(t(56, 100, "稠密负责找回，词面与显式判断负责分辨", 17, MUTED))
layers = [("第 1 层　稠密相似度", "一次 embedding", "召回改写、同义、语序变化",
           "误命中 4", MUTED),
          ("第 2 层　标识符护栏", "免费（一条正则）", "BX-07 / BX-70 这类编号必须完全一致",
           "误命中 2", VERIFY),
          ("第 3 层　模型裁判", "一次短推理", "公章 / 合同章这类纯语义的区分",
           "误命中 0", VERIFY)]
y = 150
for name, cost, does, res, col in layers:
    b.append(rect(56, y, 968, 130, PANEL, RULE))
    b.append(rect(56, y, 5, 130, col if col != MUTED else RULE, rx=0))
    b.append(t(92, y + 44, name, 22, INK, "700"))
    b.append(t(92, y + 76, does, 15, INK2))
    b.append(t(92, y + 104, f"成本：{cost}", 13, MUTED))
    b.append(t(984, y + 72, res, 26, col, "700", M, anchor="end"))
    y += 148
b.append(t(56, 626,
           "右侧是「只做到这一层」时的误命中数。第 2 层免费，且命中率一点没掉。",
           17, INK2))
render("02-fig2", W, H, "".join(b))

print(f"\n全部生成于 {OUT}")
