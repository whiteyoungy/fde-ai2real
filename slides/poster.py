#!/usr/bin/env python3
"""《FDE 十二条》朋友圈转发图。

两张，用途不同：
  方图 1440×1440   信息流里不点开就能读完，只有十二句，没有解释
  长图 1440×N      点开看的完整版：时代命题 → FDE 公理 → 六道关卡，
                   十二句按出处挂在六关上，每句配一行解释和出处

配色与字体沿用课件（deck_kit.py）与书稿构建（Noto CJK SC），
所以三样东西放在一起不打架。

**出处必须印在图上**。转发图比 PPT 更容易被截走，落款丢了、出处还在，
这句话才追得回来。带「提炼」的是为传播压缩过的版本，不是书里原句——
这一栏不能省，省了就是把压缩版冒充原句。
"""
import pathlib
from PIL import Image, ImageDraw, ImageFont

W = 1440
M = 96                      # 页边距
GROUND = (243, 245, 242)
PANEL  = (255, 255, 255)
INK    = (20, 28, 36)
INK2   = (56, 73, 90)
MUTED  = (107, 126, 143)
RULE   = (214, 221, 216)
VERIFY = (11, 142, 119)
DEEP   = (10, 75, 69)       # 第 05 句的底色
DEEPL  = (190, 214, 208)    # 深底上的辅助字
TINT   = (238, 244, 241)

SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
MONO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def f(path, size, index=2):
    return ImageFont.truetype(path, size, index=index)


TAIL = "。，、；：？！”』）】》…—"   # 这些字符不许出现在行首


def wrap(draw, text, font, maxw):
    """按像素宽换行。中文没有词边界，逐字量。

    带一条禁则：收尾标点不许被甩到下一行行首。没有这条，
    「……真实业务路径。」会变成正文一行、句号独占一行。
    """
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if draw.textlength(cur + ch, font=font) > maxw and cur:
            if ch in TAIL:          # 宁可这一行略超，也不让标点单独起行
                cur += ch; continue
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


# 十二条。短句用于方图，长句（quote_long）用于长图；两者不同的都标了「提炼」，
# 因为为版面压缩过的句子不再是书里原句。
ITEMS = [
    ("01", "FDE 的终点不是做出来，而是用起来。", None,
     "验收签字那天项目没结束，那天只是开始计时。", "上册 §15.1", "提炼"),
    ("02", "这件事降低了哪一个不确定性？降不了，别做。", None,
     "空手说“不值得做”是拒绝干活，带着证据说才是产出物。", "上册 §9.1", "逐字"),
    ("03", "第一版不是小一点的完整产品，是最窄的一条真实业务路径。", None,
     "窄，但要真——真数据、真系统、真用户。", "上册 §12.1", "提炼"),
    ("04", "Demo 证明你能做，生产证明客户敢用。", None,
     "两个环境的差距不会消失，只会累积到上线那天一次性结账。", "上册 §3.2", "提炼"),
    ("05", "没有证据，业务不该信；没有控制，安全不该放；客户不能接管，FDE 不该走。",
     "没有证据，业务不该信；\n没有控制，安全部门不该放；\n客户不能接管，FDE 不该走。",
     "一次交付必须留下的三样，各自对着一个会说“不行”的人。",
     "上册 第 9 章、§14.4", "逐字"),
    ("06", "错了只是答不好的交给模型，错了要赔钱违法的必须交给代码。",
     "错了只是答不好，可以交给模型；\n错了要赔钱或违法，必须交给代码。",
     "而且“写进提示词”不算挡住——那是请求，不是约束。", "上册 §14.2", "提炼"),
    ("07", "准确率是技术的及格线，采用率才是价值的及格线。",
     "准确率是技术团队的及格线，采用率才是这个项目产生价值的及格线。",
     "所有技术指标都是绿的、唯一不对的是没有人用——这是独立的失败。",
     "上册 §15.5", "逐字"),
    ("08", "上线成功，不等于有人能接手。", None,
     "接管四级：交文档是第零级，等于弃养；判据是能独立完成一次变更。",
     "上册 §14.6 ＋ 下册 附录 E", "合成"),
    ("09", "先定“做对了长什么样”，再动手做。", None,
     "规格不是文档，是能被引用、被检查、能进 CI 的契约。", "下册 §3.9", "逐字"),
    ("10", "方法论是工具中立的。换工具重学的是按钮，不是思维。", None,
     "读到产品名就问一句：它在这条链上补的是哪一环。", "下册 §3.1", "逐字"),
    ("11", "模型可以换，“什么算对”不能跟着换。", None,
     "芯片、系统、数据库、模型全换一遍之后，还剩什么不用重建。", "下册 §8.0", "提炼"),
    ("12", "模型是耗材，验收集才是资产。", None,
     "黄金集＋对抗集＋回归集。在非确定性系统里，它就是需求规格本身。",
     "下册 §8.0", "逐字"),
]

# 十二句不是并列的十二个观点，是一条链上的六段——这是宣讲版 quotes.py 里
# 那页「六段逻辑，一条链」的结论。方图按这六段排（CHAIN，只给方图用）。
#
# 「如果全场只留一句：第 05 句」也出自那一页——它是唯一一句同时管住业务、
# 安全和自己的判据。所以 05 在两张图上都做加重处理，不与其余十一句等权。
CHAIN = [
    ("为什么做", "这件事降低了哪一个不确定性", ["02"]),
    ("怎么做", "先定“做对了长什么样”，第一版跑最窄的真实路径", ["03", "09", "10"]),
    ("怎么验证", "什么算对，不能只存在于参与项目的人脑子里", ["11", "12"]),
    ("怎么上线", "硬约束归代码，不归提示词", ["06"]),
    ("怎么有人用", "准确率是技术及格线，采用率才是价值及格线", ["01", "04", "07"]),
    ("怎么留下", "证据、控制、接管——你走之后还剩什么", ["05", "08"]),
]
HERO = "05"
BY_NUM = {it[0]: it for it in ITEMS}
assert sum(len(c[2]) for c in CHAIN) == len(ITEMS) == 12
assert {n for c in CHAIN for n in c[2]} == set(BY_NUM)

# 长图的骨架照上册第 9 章「整条链摊开」重排：时代命题（三步）→ FDE 公理
# （风险转移）→ 六道关卡。十二句按出处挂在六关上；05 不进关，放在六关走完
# 之后当收尾判据——它本来就是骨架第三层「走到哪儿算到」，不属于任何一关。
# 措辞档位与 ITEMS 同一套规矩：逐字＝正文原句，提炼＝为版面压缩过。
ERA = [
    ("技术事实（一内一外）", "非确定性组件进了生产系统；"
     "系统正在长出面向智能体的接口。",
     "内侧：同一个输入可能给出不同输出，签约时穷举不了“做对了长什么样”。"
     "外侧：调用方从人换成智能体，流程由它现场编排，不走你修好的路。",
     "上册 第 9 章", "提炼"),
    ("管理前提被推翻", "老规则的三个挂点，同时空了。",
     "流程不固化了，节点上没人了，界面被绕过了——"
     "老问题从“可以绕过”，变成“绕不过”。",
     "上册 第 9 章", "提炼"),
    ("时代命题", "在传统软件里，管理规则大多发生在代码之外；"
     "在 AI 系统里，越来越多的管理规则必须被编译进系统本身。",
     "权限边界写进工具权限；验收标准变成验收集加流水线门禁；"
     "责任边界变成决定哪些动作允许自动执行。",
     "上册 第 9 章", "逐字"),
]
AXIOM = ("企业付的溢价买的不是代码，是把“这项技术在我们的场景里到底能不能"
         "落地”这个不确定性，转移给一个愿意对结果负责的人。",
         "这一层是公理，后面所有判据都从它推出来。它还直接推出一件商务上的事："
         "计价方式就是责任分配——按人天报价，是把风险原样退回甲方；"
         "按效果分成，是全部接过来。",
         "上册 §2.4 · 第 2 章", "逐字")
GATES = [
    ("第 1 关", "选题", "找到那件值得做的事", ["02"]),
    ("第 2 关", "定界", "把“做到哪儿算完”写成能拿出来的东西", ["09", "10"]),
    ("第 3 关", "切片", "先交最窄的一条能跑通的路", ["03"]),
    ("第 4 关", "验收", "证明这东西是对的", ["11", "12"]),
    ("第 5 关", "上线", "让它在生产环境不炸", ["04", "06"]),
    ("第 6 关", "采用", "让人真的用起来", ["01", "07", "08"]),
]
BRIDGE1 = "编译得有人干、有人担责，所以有这个岗位"
BRIDGE2 = "岗位得有方法，所以有六道关卡"
BRIDGE3 = "六关走完，风险有没有真的转移回去，判据只有一句"
assert sum(len(g[3]) for g in GATES) == 11
assert {n for g in GATES for n in g[3]} | {HERO} == set(BY_NUM)

TITLE = "FDE 十二条"
SUB = "十二句不是并列的十二个观点，是一条链上的六段"
BOOK = "《前线部署工程师（FDE）：把 AI 交付到真实世界》"
FOOT = "上册 方法与决策　·　下册 工程与系统　·　三本别册　·　12 个动手实验"


def header(d, y, sub, w=W):
    """标题区。左侧一道青色竖条，和课件封面同一个记号。"""
    d.rectangle([M, y, M + 10, y + 118], fill=VERIFY)
    d.text((M + 34, y - 6), TITLE, font=f(BOLD, 82), fill=INK)
    d.text((M + 38, y + 94), sub, font=f(SANS, 30), fill=MUTED)
    return y + 168


def tagbox(d, x, y, tag):
    """出处档位标签。逐字＝青，提炼／合成＝灰，一眼分得开。"""
    col = VERIFY if tag == "逐字" else MUTED
    ft = f(SANS, 21)
    tw = d.textlength(tag, font=ft)
    d.rounded_rectangle([x, y, x + tw + 20, y + 32], radius=6, outline=col, width=2)
    d.text((x + 10, y + 4), tag, font=ft, fill=col)
    return x + tw + 20


# ── 方图：信息流里不点开就能读完 ───────────────────────────
def square(out):
    """六段一条链，十二句挂在链上。

    左边那条竖线加六个节点，是这张图和旧版最大的差别：
    读者第一眼看到的是一条链，不是一份清单。
    行距是倒推出来的——六个段名 ＋ 十一句常规 ＋ 一句加重，正好落在 1440 里，
    改字号要重算。
    """
    H = 1440
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 238], fill=PANEL)
    d.rectangle([M, 56, M + 10, 174], fill=VERIFY)
    d.text((M + 34, 50), TITLE, font=f(BOLD, 82), fill=INK)
    d.text((M + 38, 152), SUB, font=f(SANS, 27), fill=MUTED)

    y0 = 272
    fq, fn, fb, fs = f(BOLD, 32), f(MONO, 22), f(BOLD, 30), f(SANS, 23)
    rail_x = M + 9

    # 先量一遍总高，把链条竖线一次画完（分段画会在段间断开）
    y = y0
    for _, _, nums in CHAIN:
        y += 42 + sum(70 if n == HERO else 56 for n in nums) + 14
    d.rectangle([rail_x - 2, y0 + 10, rail_x + 2, y - 28], fill=(206, 226, 220))

    y = y0
    for name, ask, nums in CHAIN:
        d.ellipse([rail_x - 10, y + 6, rail_x + 10, y + 26], fill=VERIFY)
        d.text((M + 44, y), name, font=fb, fill=VERIFY)
        d.text((M + 44 + d.textlength(name, font=fb) + 22, y + 6), ask,
               font=fs, fill=MUTED)
        y += 42
        for n in nums:
            short = BY_NUM[n][1]
            if n == HERO:
                d.rounded_rectangle([M + 40, y - 4, W - M, y + 58], radius=8,
                                    fill=DEEP)
                d.text((M + 62, y + 12), n, font=fn, fill=DEEPL)
                d.text((M + 118, y + 6), short, font=fq, fill=PANEL)
                y += 70
            else:
                d.text((M + 44, y + 6), n, font=fn, fill=VERIFY)
                d.text((M + 100, y), short, font=fq, fill=INK)
                d.line([M + 100, y + 48, W - M, y + 48], fill=RULE, width=2)
                y += 56
        y += 14

    fy = H - 128
    d.line([M, fy - 26, W - M, fy - 26], fill=RULE, width=3)
    d.text((M, fy), BOOK, font=f(BOLD, 27), fill=INK)
    d.text((M, fy + 42), "深色那一句：如果全场只留一条，留它。", font=f(SANS, 24),
           fill=INK2)
    d.text((M, fy + 80), "每一句都可以回书里核对出处。查不到的金句是负债。",
           font=f(SANS, 24), fill=MUTED)
    img.save(out)
    return img.size


# ── 长图：点开看的完整版 ───────────────────────────────────
def tall(out):
    """时代命题 → FDE 公理 → 六道关卡，十二句挂在链上。

    版面上只有两个深色块，是这条链的两端：开头是命题（管理规则必须被编译
    进系统本身），结尾是判据（第 05 句）。中间的一切都是从前者走到后者。

    出处那一栏不能省：带「提炼」的是为传播压缩过的版本，不是书里原句，
    省了就是把压缩版冒充原句。
    """
    fq, fe, fs, fn = f(BOLD, 46), f(SANS, 28), f(SANS, 24), f(MONO, 28)
    fh, fa = f(BOLD, 36), f(SANS, 26)
    usable = W - 2 * M

    def part_head(d, y, name, sub):
        d.rectangle([M, y, W - M, y + 104], fill=TINT)
        d.rectangle([M, y, M + 8, y + 104], fill=VERIFY)
        d.text((M + 28, y + 10), name, font=f(BOLD, 40), fill=INK)
        d.text((M + 28, y + 64), sub, font=fa, fill=MUTED)
        return y + 148

    def connector(d, y, label):
        cx = M + 9
        d.rectangle([cx - 2, y, cx + 2, y + 52], fill=(206, 226, 220))
        d.polygon([(cx - 9, y + 52), (cx + 9, y + 52), (cx, y + 70)],
                  fill=VERIFY)
        d.text((M + 44, y + 16), label, font=f(BOLD, 28), fill=VERIFY)
        return y + 104

    def deepblock(d, y, head, qls, els, src, tag):
        """深色块。head 是块顶那行小字，qls/els 已按 usable-44 折好。"""
        h = 36 + len(qls) * 64 + 14 + len(els) * 44 + 14 + 34 + 24
        d.rounded_rectangle([M - 20, y - 26, W - M + 20, y + h - 12],
                            radius=10, fill=DEEP)
        x = M + 20
        d.text((x, y), head, font=f(SANS, 24), fill=DEEPL)
        y += 36
        for ln in qls:
            d.text((x, y), ln, font=fq, fill=PANEL)
            y += 64
        y += 14
        for ln in els:
            d.text((x, y), ln, font=fe, fill=DEEPL)
            y += 44
        y += 14
        d.text((x, y + 2), tag + "　　" + src, font=fs, fill=DEEPL)
        return y + 34 + 60

    def qblock(d, y, qls, els, src, tag, num=None, name=None):
        """常规引句块：编号（或步骤名）、大字引句、解释、档位＋出处、分隔线。"""
        x = M
        if num is not None:
            d.text((x, y), num, font=fn, fill=VERIFY)
        if name is not None:
            xoff = 56 if num is not None else 0
            d.text((x + xoff, y + 4), name, font=f(BOLD, 26), fill=VERIFY)
        y += 40
        for ln in qls:
            d.text((x, y), ln, font=fq, fill=INK)
            y += 64
        y += 14
        for ln in els:
            d.text((x, y), ln, font=fe, fill=INK2)
            y += 44
        y += 14
        tx = tagbox(d, x, y - 4, tag)
        d.text((tx + 16, y), src, font=fs, fill=MUTED)
        y += 34 + 46
        d.line([M, y - 26, W - M, y - 26], fill=RULE, width=2)
        return y

    def render(d):
        tmp = d

        def wq(text, avail=usable):
            out = []
            for seg in text.split("\n"):
                out += wrap(tmp, seg, fq, avail)
            return out

        y = 310
        # ── 第一部分：时代命题 ──
        y = part_head(d, y, "时代命题",
                      "两条技术事实，推翻一组管理前提，逼出一条命题")
        for i, (step, qt, ex, src, tag) in enumerate(ERA):
            deep = i == len(ERA) - 1
            if deep:
                y = deepblock(d, y, "③　时代命题——前两步走到底，逼出来的",
                              wq(qt, usable - 44),
                              wrap(tmp, ex, fe, usable - 44), src, tag)
            else:
                y = qblock(d, y, wq(qt), wrap(tmp, ex, fe, usable),
                           src, tag, name="①②③"[i] + "　" + step)
        y = connector(d, y, BRIDGE1)

        # ── 第二部分：FDE 的公理 ──
        y = part_head(d, y, "FDE 的公理",
                      "风险转移——为什么会有这个岗位")
        qt, ex, src, tag = AXIOM
        y = qblock(d, y, wq(qt), wrap(tmp, ex, fe, usable), src, tag)
        y = connector(d, y, BRIDGE2)

        # ── 第三部分：六道关卡，十二条挂在关上 ──
        y = part_head(d, y, "六道关卡",
                      "岗位的方法——十二条按出处挂在六关上")
        for gnum, gname, ask, nums in GATES:
            d.rectangle([M, y, W - M, y + 92], fill=TINT)
            d.rectangle([M, y, M + 8, y + 92], fill=VERIFY)
            d.text((M + 28, y + 10), "%s　%s" % (gnum, gname), font=fh,
                   fill=INK)
            d.text((M + 28, y + 50), ask, font=fa, fill=MUTED)
            y += 136
            for n in nums:
                _, short, long_, ex, src, tag = BY_NUM[n]
                y = qblock(d, y, wq(long_ or short),
                           wrap(tmp, ex, fe, usable), src, tag, num=n)

        # ── 收尾：第 05 句 ──
        y = connector(d, y, BRIDGE3)
        _, short, long_, ex, src, tag = BY_NUM[HERO]
        y = deepblock(d, y, HERO + "　如果全场只留一条",
                      wq(long_ or short, usable - 44),
                      wrap(tmp, ex, fe, usable - 44), src, tag)

        d.line([M, y + 16, W - M, y + 16], fill=RULE, width=3)
        y += 46
        d.text((M, y), BOOK, font=f(BOLD, 30), fill=INK)
        d.text((M, y + 46), FOOT, font=f(SANS, 24), fill=MUTED)
        d.text((M, y + 88), "标“逐字”的是正文原句，“提炼”是为传播压缩的版本，"
                            "“合成”要两处论证合起来才成立。",
               font=f(SANS, 23), fill=MUTED)
        d.text((M, y + 126), "两个深色块是这条链的两端：命题，和判据。"
                             "整条推导链见 上册 第 9 章《整条链摊开》。",
               font=f(SANS, 23), fill=MUTED)
        return y + 126 + 38 + 62

    scratch = Image.new("RGB", (W, 14000), GROUND)
    H = render(ImageDraw.Draw(scratch))
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 250], fill=PANEL)
    header(d, 62, "时代命题 → FDE 的公理 → 六道关卡　·　每一句都标了出处")
    render(d)
    img.save(out)
    return img.size


if __name__ == "__main__":
    here = pathlib.Path(__file__).resolve().parent
    for name, fn in [("FDE十二条-朋友圈方图.png", square),
                     ("FDE十二条-朋友圈长图.png", tall)]:
        p = here / name
        w, h = fn(str(p))
        kb = p.stat().st_size / 1024
        print("已生成：%s  %d×%d  比例 1:%.2f  %.0f KB" % (name, w, h, h / w, kb))
