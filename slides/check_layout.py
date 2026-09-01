#!/usr/bin/env python3
"""按坐标核算 pptx 版式，替代打开文件目测。

本机禁用了 LibreOffice 转换，所以版式问题只能靠算。这个脚本把每个文本框的
实际渲染高度估出来，再检查三件事：溢出页底、文字压到下一个元素、单页元素过密。

估算口径：中日韩字符宽度按字号 1:1，拉丁与数字按 0.55，行高按字号 × 行距。
这个口径偏保守（真实字面宽度略小于字号），宁可误报，不可漏报。
"""
import sys
import pathlib
from pptx import Presentation
from pptx.util import Emu

EMU_IN = 914400.0
PAGE_H = 7.5
BOTTOM_SAFE = 7.42      # 页底安全线
OVERLAP_TOL = 0.04      # 允许的重叠容差（英寸）


def is_cjk(ch):
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF
            or 0xFF00 <= o <= 0xFFEF or 0x3000 <= o <= 0x303F)


def text_width_units(text):
    """返回以“1 个全角字宽”为单位的行宽。"""
    w = 0.0
    for ch in text:
        if ch in ' 　':
            w += 1.0 if ch == '　' else 0.3
        elif is_cjk(ch):
            w += 1.0
        else:
            w += 0.55
    return w


def para_height(p, box_w_in):
    """估一个段落渲染后占的高度（英寸）。"""
    runs = p.runs
    if not runs:
        return 0.0
    size = max((r.font.size.pt if r.font.size else 18) for r in runs)
    text = ''.join(r.text for r in runs)
    if not text.strip():
        return 0.0
    char_in = size / 72.0
    per_line = max(1.0, box_w_in / char_in)
    lines = max(1, int(text_width_units(text) / per_line) + 1)
    ls = p.line_spacing if isinstance(p.line_spacing, float) else 1.0
    sb = p.space_before.pt if p.space_before else 0
    sa = p.space_after.pt if p.space_after else 0
    return lines * char_in * ls + (sb + sa) / 72.0


def blocks(slide):
    out = []
    for sh in slide.shapes:
        x, y = sh.left / EMU_IN, sh.top / EMU_IN
        w, h = sh.width / EMU_IN, sh.height / EMU_IN
        if not sh.has_text_frame:
            out.append(dict(kind='shape', x=x, y=y, w=w, h=h, bot=y + h, text=''))
            continue
        tf = sh.text_frame
        txt = tf.text
        if not txt.strip():
            out.append(dict(kind='shape', x=x, y=y, w=w, h=h, bot=y + h, text=''))
            continue
        need = sum(para_height(p, w) for p in tf.paragraphs)
        # 文本框的 h 只是个标称值——word_wrap 开着、不自动缩放时，文字从顶部往下
        # 排，实际底部由 need 决定，跟 h 无关。早前用 max(h, need) 算出 327 处
        # 假碰撞，就是把这个标称高度当成了渲染高度。
        out.append(dict(kind='text', x=x, y=y, w=w, h=h,
                        bot=y + need, need=need, text=txt))
    return out


def container_of(b, bs):
    """找包住这块文字的卡片／例子框（面积最小的那个）。"""
    best = None
    for c in bs:
        if c['kind'] != 'shape' or c['h'] < 0.3:
            continue
        if (c['x'] - 0.02 <= b['x'] and c['y'] - 0.02 <= b['y']
                and c['x'] + c['w'] + 0.02 >= b['x'] + b['w']
                and c['y'] + c['h'] > b['y']):
            if best is None or c['w'] * c['h'] < best['w'] * best['h']:
                best = c
    return best


def check(path):
    prs = Presentation(path)
    problems = []
    for i, slide in enumerate(prs.slides, 1):
        bs = blocks(slide)
        texts = [b for b in bs if b['kind'] == 'text']
        # 1) 溢出页底
        for b in texts:
            if b['bot'] > BOTTOM_SAFE:
                problems.append((i, 'OVERFLOW',
                                 '底部 %.2f\" 超出安全线 %.2f\"：%s'
                                 % (b['bot'], BOTTOM_SAFE, b['text'][:40])))
        # 2) 卡片／例子框里的文字撑破了框
        for b in texts:
            box = container_of(b, bs)
            if box is None:
                continue
            room = box['y'] + box['h'] - b['y'] - 0.10
            if b['need'] > room:
                problems.append((i, 'BURST',
                                 '框内文字需 %.2f\" 但只剩 %.2f\"：%s'
                                 % (b['need'], room, b['text'][:34])))
        # 3) 文字压到下方元素
        for a in texts:
            if container_of(a, bs) is not None:
                continue                          # 框内文字上一步已查
            for c in bs:
                if c is a or c['y'] <= a['y'] + 0.02:
                    continue
                if a['x'] + a['w'] <= c['x'] + 0.02 or c['x'] + c['w'] <= a['x'] + 0.02:
                    continue                      # 水平不相交
                if c['h'] < 0.05:                 # 分隔线，允许被贴近
                    continue
                if a['bot'] > c['y'] + OVERLAP_TOL:
                    problems.append((i, 'COLLIDE',
                                     '“%s…” 底部 %.2f\" 压到 %.2f\" 处的元素 “%s…”'
                                     % (a['text'][:22], a['bot'], c['y'],
                                        (c['text'] or '(图形)')[:22])))
        # 4) 单页文字量
        chars = sum(len(b['text']) for b in texts)
        if chars > 1150:
            problems.append((i, 'DENSE', '本页 %d 字，偏密' % chars))
    return prs, problems


def main():
    files = sys.argv[1:] or sorted(
        str(p) for p in pathlib.Path(__file__).resolve().parent.glob('*.pptx'))
    bad = 0
    for f in files:
        prs, probs = check(f)
        name = pathlib.Path(f).name
        n = len(prs.slides._sldIdLst)
        if not probs:
            print('✔ %s：%d 页，无溢出、无碰撞' % (name, n))
            continue
        bad += 1
        print('✘ %s：%d 页，%d 处' % (name, n, len(probs)))
        for pg, kind, msg in probs:
            print('   p%-3d %-9s %s' % (pg, kind, msg))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
