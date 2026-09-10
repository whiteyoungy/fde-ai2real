# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""《智能体来了之后，管理规则没地方待了》—— 信息图 v2。

版面是一张 100 单位宽的栅格，所有尺寸都以 s 为单位写死，
所以同一份排版可以精确地落进任何画幅：先量出总高 U，再解 s = min(W/100, H/U)。
文字换行也是尺度无关的（字号和栏宽同比例缩放），量一遍就够。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vizkit import *

# ── 左栏：传统软件时代 ────────────────────────────────────
def col_left(cv, x, y, w):
    s = cv.s; y0 = y
    cv.rect(x, y, w, 3.3*s, fill=NAVY)
    cv.text(x, y+0.72*s, "传统软件时代：楚河汉界明确", 1.95, PANEL, True, align="c", box=w)
    y += 4.1*s
    y += cv.text(x, y, "分工边界：代码管确定的，人管不确定的", 1.72, NAVY, True,
                 align="c", box=w) + 0.9*s

    SC = 24.6*s
    cv.rect(x, y, w, SC, fill=PANEL, outline=LGREY, r=0.6*s)
    pad = 0.9*s
    wallw = 5.8*s
    wx = x + (w - wallw)/2
    halfw = (w - wallw)/2 - pad*1.9
    lx, rx = x+pad, wx+wallw+1.5*s
    cv.text(lx, y+1.0*s, "代码可确定", 1.42, BLUE, True)
    cv.text(lx, y+2.9*s, "系统内侧", 1.14, GREY, False)
    cv.text(rx, y+1.0*s, "人处理不确定", 1.42, NAVY2, True)
    cv.text(rx, y+2.9*s, "系统外侧", 1.14, GREY, False)
    gy = y + 5.0*s
    wall(cv, wx, gy-0.8*s, wallw, SC-(gy-y)-1.0*s)
    # 左：屏幕里跑固化流程 + 一个库
    gw = min(halfw*0.90, 11.0*s)
    gx = lx + (halfw - gw)/2
    ic_screen(cv, gx, gy, gw, 7.2*s)
    ic_flow(cv, gx+gw*0.16, gy+1.2*s, gw*0.68, 3.9*s)
    ic_db(cv, gx+gw*0.32, gy+8.4*s, gw*0.36, 4.3*s)
    # 右：四个兜底的人
    px0 = rx + max(0.0, (halfw - 9.0*s)/2)
    for i, t in enumerate(("审批人", "处理例外", "客服坐席", "补录数据")):
        cy = gy + 1.6*s + i*3.3*s
        ic_person(cv, px0+1.4*s, cy, 1.28*s)
        cv.text(px0+3.4*s, cy-0.80*s, t, 1.30, INK, False)
    capy = y + SC - 4.4*s
    cv.text(lx, capy, "流程＋数据，固化执行。同一个输入，永远同一个结果。",
            1.10, GREY, False, halfw, 1.32)
    cv.text(rx, capy, "节点上的人接住例外——用人当柔性胶水。",
            1.10, GREY, False, halfw, 1.32)
    y += SC + 1.0*s

    bw = (w-1.2*s)/2
    bh = 7.4*s
    for i, (t, items, col) in enumerate([
            ("系统能力边界清晰", ["流程固化", "界面固定", "权限可控"], BLUE),
            ("用人当柔性胶水", ["节点上的人兜底", "经验判断", "灵活处理"], NAVY2)]):
        bx = x + i*(bw+1.2*s)
        cv.rect(bx, y, bw, bh, fill=PANEL, outline=LGREY, r=0.5*s)
        cv.rect(bx, y, bw, 0.30*s, fill=col)
        cv.text(bx+0.9*s, y+0.95*s, t, 1.36, col, True, bw-1.8*s)
        for j, it in enumerate(items):
            yy = y+3.2*s + j*1.75*s
            cv.rect(bx+1.0*s, yy+0.42*s, 0.42*s, 0.42*s, fill=col)
            cv.text(bx+2.0*s, yy, it, 1.18, INK, False, bw-2.8*s)
    y += bh + 1.2*s

    cv.rect(x, y, w, 2.7*s, fill=NAVY2)
    cv.text(x, y+0.52*s, "管理规则的三大挂点", 1.5, PANEL, True, align="c", box=w)
    y += 3.4*s
    cw_ = (w-1.6*s)/3
    hooks = [("固化的流程", "系统只让你按这个顺序走"),
             ("节点上的人", "岗位职责写着谁负责"),
             ("界面权限", "人只能点系统给他的按钮")]
    hh = 7.2*s
    for i, (t, dsc) in enumerate(hooks):
        hx = x + i*(cw_+0.8*s)
        cv.rect(hx, y, cw_, hh, fill=NAVY)
        cv.text(hx+0.7*s, y+0.9*s, t, 1.34, PANEL, True, cw_-1.4*s, 1.24)
        cv.text(hx+0.7*s, y+3.4*s, dsc, 1.10, PALE, False, cw_-1.4*s, 1.30)
    return y + hh - y0


# ── 中栏：AI 时代 ────────────────────────────────────────
def sub_panel(cv, x, y, w, which, IH=None):
    """①内侧 / ②外侧。IH 给了就按这个高度画外框，否则只量自然高。"""
    s = cv.s
    if which == 0:
        title, sub2 = "① 内侧冲击", "非确定性进入了系统"
        cap = "系统自己开始产出不确定的结果"
        core = "AI 模型 / 智能体"
        tail = "…… 同一个问题问两遍，答案可能不一样"
        a1, a2 = "同一输入  ≠  同一输出", "签合同的时候，穷举不了「做对了长什么样」"
    else:
        title, sub2 = "② 外侧冲击", "系统长出面向智能体的接口"
        cap = "每个系统都在给它配一把能直接开门的钥匙"
        core = "MCP 等标准接口"
        tail = "…… 调用方从人，变成了它"
        a1, a2 = "运行时现场编排", "直接调用能力，不点按钮——按钮上的权限管不着它"
    if IH is not None:
        cv.rect(x, y, w, IH, fill=PANEL, outline=(214, 206, 236), r=0.6*s)
        cv.rect(x, y, w, 0.34*s, fill=VIO2)
    iw = w - 1.8*s
    yy = y + 1.1*s
    yy += cv.text(x+0.9*s, yy, title, 1.50, VIO, True, iw, 1.24) + 0.35*s
    yy += cv.text(x+0.9*s, yy, sub2, 1.34, VIO, True, iw, 1.24) + 0.55*s
    yy += cv.text(x+0.9*s, yy, cap, 1.10, GREY, False, iw, 1.32) + 1.1*s
    cv.rect(x+w*0.10, yy, w*0.80, 3.1*s, fill=VIOL, outline=VIO, r=0.5*s)
    cv.text(x+w*0.10, yy+0.80*s, core, 1.28, VIO, True, align="c", box=w*0.80)
    yy += 3.1*s
    for k in range(3):
        cx = x + w*(0.22+k*0.28)
        arrow_d(cv, cx, yy+0.5*s, yy+2.5*s, (170, 160, 200))
    yy += 2.7*s
    if which == 0:
        for k in range(3):
            cx = x + w*(0.22+k*0.28)
            cv.rect(cx-w*0.115, yy, w*0.23, 2.5*s, fill=(247, 245, 252),
                    outline=(206, 198, 230), r=0.4*s)
            cv.text(cx-w*0.115, yy+0.58*s, "结果 " + "ABC"[k], 1.10, VIO, False,
                    align="c", box=w*0.23)
        yy += 2.5*s
    else:
        for k in range(3):
            cx = x + w*(0.22+k*0.28)
            ic_robot(cv, cx, yy+1.9*s, 1.45*s)
            cv.text(cx-w*0.14, yy+3.5*s, ["智能体 1", "智能体 2", "智能体 N"][k],
                    1.02, VIO, False, align="c", box=w*0.28)
        yy += 5.1*s
    yy += 0.7*s
    yy += cv.text(x+0.9*s, yy, tail, 1.10, GREY, False, iw, 1.32) + 1.0*s
    ah = (cv.th(a1, 1.30, iw-1.6*s, 1.24) + 0.45*s
          + cv.th(a2, 1.10, iw-1.6*s, 1.32) + 1.8*s)
    if IH is not None:
        yy = y + IH - 1.0*s - ah
    cv.rect(x+0.9*s, yy, iw, ah, fill=(255, 245, 236), outline=ORANGE, r=0.5*s)
    h1 = cv.text(x+1.7*s, yy+0.9*s, a1, 1.30, ORANGE, True, iw-1.6*s, 1.24)
    cv.text(x+1.7*s, yy+0.9*s+h1+0.45*s, a2, 1.10, INK, False, iw-1.6*s, 1.32)
    return yy + ah + 1.0*s - y


def col_mid(cv, x, y, w):
    s = cv.s; y0 = y
    cv.rect(x, y, w, 3.3*s, fill=VIO)
    cv.text(x, y+0.72*s, "智能体来了之后：楚河汉界从两头被拆掉", 1.95, PANEL, True,
            align="c", box=w)
    y += 4.1*s
    y += cv.text(x, y, "内侧和外侧，同时被拆", 1.72, VIO, True, align="c", box=w) + 0.9*s

    pw = (w-1.4*s)/2
    keep = cv.dry; cv.dry = True
    IH = max(sub_panel(cv, 0, 0, pw, 0), sub_panel(cv, 0, 0, pw, 1))
    cv.dry = keep
    sub_panel(cv, x, y, pw, 0, IH)
    sub_panel(cv, x+pw+1.4*s, y, pw, 1, IH)
    y += IH + 1.2*s

    cv.rect(x, y, w, 2.9*s, fill=RED)
    cv.text(x, y+0.58*s, "两侧冲击的共同结果：三大挂点同时失效", 1.56, PANEL, True,
            align="c", box=w)
    y += 3.6*s
    cw_ = (w-1.6*s)/3
    hh = 10.8*s
    outs = [("流程不固化了", "它在运行时现场编排，不走你修好的路"),
            ("节点上没人了", "原来靠人兜住不确定性的位置，被撤掉了"),
            ("界面被绕过了", "它直接调用能力，按钮上的权限管不着它")]
    for i, (t, dsc) in enumerate(outs):
        hx = x + i*(cw_+0.8*s)
        cv.rect(hx, y, cw_, hh, fill=REDL, outline=RED, r=0.5*s)
        cv.text(hx+0.6*s, y+0.9*s, t, 1.34, RED, True, cw_-1.2*s, 1.24)
        bx, by, bw2, bh2 = hx+cw_*0.16, y+3.4*s, cw_*0.68, 3.0*s
        cv.dash(bx, by, bw2, bh2, (200, 150, 142), max(1, s*0.13), seg=0.9*s, gap=0.6*s)
        ic_cross(cv, bx+bw2/2, by+bh2/2, 1.05*s, RED)
        cv.text(hx+0.6*s, y+7.2*s, dsc, 1.10, INK, False, cw_-1.2*s, 1.30)
    return y + hh - y0


# ── 右栏：理论适用前提的强度变化 ──────────────────────────
THEORY = [
    ("公理层", [("不完全契约",
                 "同一输入可能给出不同输出，签的时候穷举不了「做对了长什么样」")]),
    ("过程层", [("阶段—关口",
                 "失败率回到新产品开发的水平，关口重新变成真的否决点"),
                ("多任务委托代理（古德哈特）",
                 "准确率极易测、业务价值极难测——这是它的最坏情形"),
                ("正常事故理论",
                 "非确定组件 ＋ 自动执行动作 ＋ 跨系统调用，风险同时上升"),
                ("社会—技术系统",
                 "判断权归谁变了：调用方换成智能体之后，不重设权责必然反弹")]),
    ("资产层", [("吸收能力",
                 "模型与数据分布一直在变，接不住的，几个月后就停了"),
                ("组织知识创造",
                 "验收集第一次给了它可计算的载体：黄金集、对抗集、回归集")]),
]

def col_right(cv, x, y, w):
    s = cv.s; y0 = y
    cv.rect(x, y, w, 3.3*s, fill=TEAL)
    cv.text(x, y+0.72*s, "理论适用前提的强度变化", 1.95, PANEL, True, align="c", box=w)
    y += 4.1*s
    y += cv.text(x, y, "八条老理论，AI 把它们的前提换了", 1.30, GREY, False,
                 align="c", box=w) + 1.2*s
    for tag, items in THEORY:
        tw_ = cv.tw(tag, 1.22, True) + 1.6*s
        cv.rect(x, y, tw_, 2.3*s, fill=(226, 242, 240), r=1.15*s)
        cv.text(x, y+0.42*s, tag, 1.22, TEAL, True, align="c", box=tw_)
        y += 3.0*s
        for t, dsc in items:
            h1 = cv.text(x+1.5*s, y, t, 1.30, NAVY, True, w-1.5*s, 1.26)
            h2 = cv.text(x+1.5*s, y+h1+0.30*s, dsc, 1.10, GREY, False, w-1.5*s, 1.34)
            cv.rect(x, y+0.34*s, 0.55*s, h1+h2, fill=TEAL)
            y += h1 + h2 + 1.55*s
        y += 0.5*s
    return y - y0


# ── 底部结论条 ────────────────────────────────────────────
def band(cv, x, y, w):
    s = cv.s; y0 = y
    cv.rect(x, y, w, 3.2*s, fill=NAVY)
    cv.text(x, y+0.62*s, "结论：管理规则必须被编译进系统本身", 2.0, PANEL, True,
            align="c", box=w)
    y += 3.2*s
    BH = 13.4*s
    cv.rect(x, y, w, BH, fill=WARM, outline=WARMB, r=0.5*s)
    aw = 3.6*s
    bw = (w - aw*2 - 2.4*s)/3
    cols = [
        ("传统软件：规则在代码之外", GREY, NAVY2,
         ["权限边界　写在制度里", "验收标准　在验收会上讨论", "责任边界　写在岗位职责里"]),
        ("AI 时代：规则必须编译进系统", VIO, VIO,
         ["权限边界　→　RBAC 与工具权限", "验收标准　→　验收集 ＋ 流水线门禁",
          "责任边界　→　智能体的动作授权边界"]),
        ("于是从「可绕过」变成「绕不过」", ORANGE, ORANGE,
         ["内侧变化　规则写不成死流程", "外侧变化　挂规则的地方被抽掉",
          "结果　不编译进系统，就没有地方可待"]),
    ]
    for i, (t, tc, ac, items) in enumerate(cols):
        bx = x + 0.6*s + i*(bw+aw)
        cv.rect(bx, y+1.0*s, bw, BH-2.0*s, fill=PANEL, outline=LGREY, r=0.5*s)
        cv.rect(bx, y+1.0*s, 0.34*s, BH-2.0*s, fill=ac)
        cv.text(bx+1.1*s, y+1.9*s, t, 1.42, tc, True, bw-2.2*s, 1.26)
        for j, it in enumerate(items):
            cv.text(bx+1.1*s, y+5.1*s + j*2.5*s, it, 1.16, INK, False, bw-2.2*s, 1.28)
        if i < 2:
            arrow_r(cv, bx+bw+0.7*s, y+BH/2-1.5*s, aw-1.4*s, 3.0*s, ORANGE)
    return y + BH - y0


# ── 总装 ──────────────────────────────────────────────────
TITLE = "智能体来了之后，管理规则没地方待了"
SUB = ("传统企业软件有一条从没写进任何文档、所有人却都照着执行的楚河汉界："
       "代码管确定的，人管不确定的。AI 是从两头同时拆它的——"
       "不确定性从「可绕过」变成了「绕不过」。")

def layout(cv, GW, x0=0.0, y0=0.0, slack=0.0, draw=False):
    """按 GW（单位数）宽的栅格排一遍。draw=False 时只量高。"""
    s = cv.s
    cw = (GW - 5.2)*s
    y = y0 + 2.6*s + slack*0.28
    y += cv.text(x0, y, TITLE, 4.3, NAVY, True, cw, 1.20) + 0.8*s
    if draw:
        cv.rect(x0, y-0.2*s, cw*0.115, 0.42*s, fill=ORANGE)
    y += 1.0*s
    y += cv.text(x0, y, SUB, 1.42, GREY, False, cw, 1.40) + 2.2*s + slack*0.28
    avail = cw - 1.8*s*2
    wl, wm, wr = avail*0.345, avail*0.400, avail*0.255
    hl = col_left(cv, x0, y, wl)
    hm = col_mid(cv, x0+wl+1.8*s, y, wm)
    hr = col_right(cv, x0+wl+wm+3.6*s, y, wr)
    hc = max(hl, hm, hr)
    # 两栏之间的方向箭头：传统 → AI
    if draw:
        ay = y + hl*0.34
        arrow_r(cv, x0+wl+0.15*s, ay, 1.5*s, 2.6*s, ORANGE)
    y += hc + 2.2*s + slack*0.44
    y += band(cv, x0, y, cw)
    return y - y0 + 2.6*s


def solve(W, H, gw_cap=200.0):
    """解出栅格宽度 GW，让 GW : U 正好等于画幅比例。U 随 GW 变（文字换行会变），
    所以迭代几轮。"""
    REF = 22.0
    G = 100.0
    for _ in range(10):
        cv = Cv(8, 8, REF); cv.dry = True
        U = layout(cv, G)/REF
        target = (W/H)*U
        if abs(target - G) < 0.4:
            G = target; break
        G = min(gw_cap, G + (target - G)*0.8)
        if G >= gw_cap: break
    cv = Cv(8, 8, REF); cv.dry = True
    U = layout(cv, G)/REF
    return G, U


def render(W, H, path, gw_cap=200.0):
    G, U = solve(W, H, gw_cap)
    s = min(W/G, H/U)
    cv = Cv(W, H, s); cv.dry = True
    used = layout(cv, G)
    cv.dry = False
    slack = max(0.0, H - used)
    x0 = (W - (G - 5.2)*s)/2
    layout(cv, G, x0, 0.0, slack, draw=True)
    cv.rect(0, 0, W, W*0.008, fill=NAVY)
    cv.rect(0, H-W*0.008, W, W*0.008, fill=NAVY)
    cv.img.save(path, "PNG")
    print("ok", os.path.basename(path), f"{W}x{H} grid={G:.1f}x{U:.1f} s={s:.2f} "
          f"用宽 {(G-5.2)*s/W*100:.0f}%")


OUT = os.path.dirname(os.path.abspath(__file__))
# 书稿用整页横版彩插（正文里旋转 90° 排入），300dpi A4 横幅。
render(3508, 2480, OUT + "/智能体来了之后-A4横版300dpi.png")
