# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""信息图渲染小工具：字体、换行、量/画双模画布、几个矢量图标。"""
from PIL import Image, ImageDraw, ImageFont

SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
IDX = 2

GROUND = (246, 247, 250)
PANEL  = (255, 255, 255)
INK    = (31, 39, 51)
NAVY   = (17, 43, 74)
NAVY2  = (27, 63, 102)
BLUE   = (43, 108, 176)
BLUEL  = (219, 231, 244)
VIO    = (91, 71, 158)
VIOL   = (233, 228, 246)
VIO2   = (126, 105, 190)
TEAL   = (23, 154, 143)
ORANGE = (217, 111, 43)
RED    = (192, 58, 43)
REDL   = (252, 235, 232)
GREY   = (107, 116, 128)
GREY2  = (150, 158, 168)
LGREY  = (223, 228, 234)
PALE   = (199, 216, 232)
WARM   = (253, 245, 234)
WARMB  = (233, 214, 187)
STONE  = (104, 112, 122)
STONE2 = (78, 86, 96)
WATER  = (176, 208, 232)
GOLD   = (240, 201, 154)

_fc = {}
def F(p, sz):
    k = (p, max(6, int(sz)))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(p, max(6, int(sz)), index=IDX)
    return _fc[k]

TAIL = "。，、；：？！」』）】》…—·"
LAT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.%/-+≠")

def toks(t):
    out, buf = [], ""
    for ch in t:
        if ch in LAT:
            buf += ch
        else:
            if buf: out.append(buf); buf = ""
            out.append(ch)
    if buf: out.append(buf)
    return out

def wrap(d, t, f, mw):
    lines, cur = [], ""
    for tk in toks(t):
        if tk == "\n":
            lines.append(cur); cur = ""; continue
        if d.textlength(cur + tk, font=f) > mw and cur:
            if tk in TAIL:
                cur += tk; continue
            lines.append(cur); cur = tk.lstrip()
        else:
            cur += tk
    if cur: lines.append(cur)
    return lines


class Cv:
    """dry=True 时只量高不落墨——同一段排版代码跑两遍，第一遍算总高。"""
    def __init__(self, w, h, s, bg=GROUND):
        self.W, self.H, self.s = w, h, s
        self.img = Image.new("RGB", (w, h), bg)
        self.d = ImageDraw.Draw(self.img)
        self.dry = False

    # 基本图元
    def rect(self, x, y, w, h, fill=None, outline=None, lw=None, r=0):
        if self.dry: return
        lw = int(lw if lw is not None else max(1, self.s * 0.08))
        bb = [x, y, x + w, y + h]
        if r:
            self.d.rounded_rectangle(bb, radius=r, fill=fill, outline=outline, width=lw)
        else:
            self.d.rectangle(bb, fill=fill, outline=outline, width=lw)

    def line(self, x0, y0, x1, y1, color, lw=None):
        if self.dry: return
        self.d.line([x0, y0, x1, y1], fill=color, width=int(lw or max(1, self.s * 0.10)))

    def poly(self, pts, fill=None, outline=None, lw=None):
        if self.dry: return
        self.d.polygon(pts, fill=fill, outline=outline, width=int(lw or 1))

    def ell(self, x, y, w, h, fill=None, outline=None, lw=None):
        if self.dry: return
        self.d.ellipse([x, y, x + w, y + h], fill=fill, outline=outline,
                       width=int(lw or max(1, self.s * 0.08)))

    def dash(self, x, y, w, h, color, lw=None, seg=None, gap=None):
        if self.dry: return
        s = self.s
        seg = seg or s * 1.0; gap = gap or s * 0.7
        lw = int(lw or max(1, s * 0.10))
        def ln(x0, y0, x1, y1):
            L = ((x1-x0)**2 + (y1-y0)**2) ** 0.5 or 1
            n = int(L / (seg + gap)) + 1
            for i in range(n):
                a = i * (seg + gap) / L
                b = min(1.0, (i * (seg + gap) + seg) / L)
                if a >= 1: break
                self.d.line([x0+(x1-x0)*a, y0+(y1-y0)*a, x0+(x1-x0)*b, y0+(y1-y0)*b],
                            fill=color, width=lw)
        ln(x, y, x+w, y); ln(x, y+h, x+w, y+h); ln(x, y, x, y+h); ln(x+w, y, x+w, y+h)

    # 文字
    def text(self, x, y, t, size, color=INK, bold=False, maxw=None, lead=1.34,
             align="l", box=None):
        f = F(BOLD if bold else SANS, size * self.s)
        lines = wrap(self.d, t, f, maxw if maxw else 10**7)
        lh = size * self.s * lead
        if not self.dry:
            for i, ln in enumerate(lines):
                xx = x
                if align == "c": xx = x + (box - self.d.textlength(ln, font=f)) / 2
                elif align == "r": xx = x + box - self.d.textlength(ln, font=f)
                self.d.text((xx, y + i * lh), ln, font=f, fill=color)
        return lh * len(lines)

    def th(self, t, size, maxw=None, lead=1.34):
        k = self.dry; self.dry = True
        h = self.text(0, 0, t, size, INK, False, maxw, lead)
        self.dry = k
        return h

    def tw(self, t, size, bold=False):
        return self.d.textlength(t, font=F(BOLD if bold else SANS, size * self.s))


# ── 矢量图标 ──────────────────────────────────────────────
def ic_person(cv, cx, cy, r, col=NAVY2):
    """西装小人剪影。cy 是整体竖向中心。"""
    if cv.dry: return
    hr = r * 0.40
    cv.ell(cx - hr, cy - r, hr * 2, hr * 2, fill=col)
    cv.d.pieslice([cx - r * 0.85, cy - r * 0.10, cx + r * 0.85, cy + r * 1.6],
                  180, 360, fill=col)

def ic_robot(cv, cx, cy, r, col=VIO):
    """智能体：天线 + 方头 + 两只眼 + 身子。"""
    if cv.dry: return
    cv.line(cx, cy - r * 1.28, cx, cy - r * 0.92, col, max(1, r * 0.14))
    cv.ell(cx - r * 0.16, cy - r * 1.48, r * 0.32, r * 0.32, fill=col)
    cv.rect(cx - r * 0.78, cy - r * 0.92, r * 1.56, r * 1.16, fill=col, r=r * 0.30)
    cv.ell(cx - r * 0.44, cy - r * 0.54, r * 0.26, r * 0.26, fill=PANEL)
    cv.ell(cx + r * 0.18, cy - r * 0.54, r * 0.26, r * 0.26, fill=PANEL)
    cv.rect(cx - r * 0.62, cy + r * 0.36, r * 1.24, r * 0.72, fill=col, r=r * 0.20)

def ic_cross(cv, cx, cy, r, col=RED, lw=None):
    if cv.dry: return
    lw = lw or max(2, r * 0.34)
    cv.line(cx - r, cy - r, cx + r, cy + r, col, lw)
    cv.line(cx + r, cy - r, cx - r, cy + r, col, lw)

def ic_flow(cv, x, y, w, h, col=BLUE):
    """流程图小图：三个方块 + 连线。"""
    if cv.dry: return
    bw, bh = w * 0.30, h * 0.26
    cv.rect(x, y, bw, bh, fill=BLUEL, outline=col, r=bh * 0.25)
    cv.rect(x + w - bw, y, bw, bh, fill=BLUEL, outline=col, r=bh * 0.25)
    cv.rect(x + (w - bw) / 2, y + h - bh, bw, bh, fill=BLUEL, outline=col, r=bh * 0.25)
    cv.line(x + bw, y + bh / 2, x + w - bw, y + bh / 2, col)
    cv.line(x + w / 2, y + bh, x + w / 2, y + h - bh, col)

def ic_db(cv, x, y, w, h, col=BLUE):
    if cv.dry: return
    eh = h * 0.28
    cv.rect(x, y + eh / 2, w, h - eh, fill=BLUEL, outline=None, lw=1)
    cv.line(x, y + eh / 2, x, y + h - eh / 2, col)
    cv.line(x + w, y + eh / 2, x + w, y + h - eh / 2, col)
    cv.ell(x, y + h - eh, w, eh, fill=BLUEL, outline=col)
    cv.ell(x, y, w, eh, fill=PANEL, outline=col)

def ic_screen(cv, x, y, w, h, col=BLUE):
    if cv.dry: return
    cv.rect(x, y, w, h * 0.76, fill=PANEL, outline=col, r=h * 0.06)
    cv.rect(x + w * 0.42, y + h * 0.76, w * 0.16, h * 0.14, fill=col)
    cv.rect(x + w * 0.24, y + h * 0.90, w * 0.52, h * 0.10, fill=col, r=h * 0.05)

def arrow_r(cv, x, y, w, h, fill=ORANGE):
    """块状右向箭头。"""
    if cv.dry: return
    sw = w * 0.58
    cv.poly([(x, y + h * 0.26), (x + sw, y + h * 0.26), (x + sw, y),
             (x + w, y + h / 2), (x + sw, y + h), (x + sw, y + h * 0.74),
             (x, y + h * 0.74)], fill=fill)

def arrow_d(cv, cx, y0, y1, col=GREY2, lw=None):
    if cv.dry: return
    lw = lw or max(1, cv.s * 0.10)
    cv.line(cx, y0, cx, y1 - cv.s * 0.55, col, lw)
    cv.poly([(cx - cv.s * 0.34, y1 - cv.s * 0.60), (cx + cv.s * 0.34, y1 - cv.s * 0.60),
             (cx, y1)], fill=col)

def wall(cv, x, y, w, h, chars="楚河汉界"):
    """城墙：垛口 + 墙体 + 竖排字。左侧带一条河。"""
    if cv.dry: return
    s = cv.s
    rw = w * 0.34                       # 河宽
    wx, ww = x + rw, w - rw
    # 河：两条波浪带
    cv.rect(x, y + h * 0.04, rw * 0.86, h * 0.94, fill=WATER)
    for i in range(9):
        yy = y + h * 0.08 + i * h * 0.105
        cv.line(x + rw * 0.10, yy, x + rw * 0.62, yy + h * 0.020, (222, 238, 250),
                max(1, s * 0.09))
    # 垛口
    ch = h * 0.075
    n = 5
    bw = ww / (n * 2 - 1)
    for i in range(n):
        cv.rect(wx + i * bw * 2, y, bw, ch * 2, fill=STONE2)
    cv.rect(wx, y + ch * 1.6, ww, h - ch * 1.6, fill=STONE)
    # 砖缝
    rows = 7
    rh = (h - ch * 1.6) / rows
    for i in range(1, rows):
        cv.line(wx, y + ch * 1.6 + i * rh, wx + ww, y + ch * 1.6 + i * rh, STONE2,
                max(1, s * 0.05))
    # 竖排字
    fs = ww * 0.56
    f = F(BOLD, fs)
    tot = len(chars) * fs * 1.14
    ty = y + ch * 1.6 + (h - ch * 1.6 - tot) / 2
    for i, c in enumerate(chars):
        tw_ = cv.d.textlength(c, font=f)
        cv.d.text((wx + (ww - tw_) / 2, ty + i * fs * 1.14), c, font=f, fill=PANEL)
