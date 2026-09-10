#!/usr/bin/env python3
"""案例场景图。

**为什么要有这个文件。** 课件讲六道关卡时引的都是判据和产物，
学员记得住条目，但记不住「这件事发生在哪儿」。而书里那批一手案例
恰好都有很具体的现场——病房、边检口、呼叫中心、产线。
场景一旦具象，判据就跟着有了挂靠点：
「阈值 ≥6 时八次告警才有一例真的」比「阳性预测值 0.12」记得住得多。

**画法上的三条约束：**

1. **不画细节，画关系。** 人是圆头加圆角身子，设备是方块——
   分辨率再高也只有一眼时间，细节反而盖住结构。
2. **数字进画面，不进图注。** 图注会被裁掉，画里的数字不会。
   每张图放二到四个数字，各自贴在它描述的那个东西旁边。
3. **配色承担语义**，沿用 artifacts.py：青＝成立／已验证，
   琥珀＝存疑，砖红＝失败／误报，灰＝背景。

所有场景图都基于书中有一手来源的案例，因此**不盖「教学示例」戳**，
改在右下角标出处（哪份报告／哪篇论文），与 artifacts.py 里那批造的图区分开。
"""
import pathlib
from PIL import Image, ImageDraw

from artifacts import (OUT, W, PAD, f, new, box, t, wrap,
                       GROUND, PANEL, INK, INK2, MUTED, RULE,
                       VERIFY, CAVEAT, WRONG, TINT, WTINT, CTINT, DEEP)

HS = 940                     # 场景图统一高度，宽高比 2.55


# ── 场景元件 ────────────────────────────────────────────────
def person(d, x, y, h=110, col=INK2, head=None):
    """一个人：圆头 + 圆角身子。x,y 是脚底中点。"""
    hr = h * 0.26
    d.ellipse([x - hr, y - h, x + hr, y - h + 2 * hr],
              fill=head or col)
    bw = h * 0.42
    d.rounded_rectangle([x - bw, y - h + 2 * hr + h * 0.06, x + bw, y],
                        radius=int(h * 0.22), fill=col)


def bed(d, x, y, w=250, h=96, occupied=True):
    """病床，侧视。x,y 左上角。"""
    box(d, x, y + h * 0.30, w, h * 0.42, fill=PANEL, outline=RULE, width=3, r=10)
    d.rounded_rectangle([x, y, x + w * 0.20, y + h * 0.72],
                        radius=8, fill=RULE)
    for lx in (x + 14, x + w - 14):
        d.line([lx, y + h * 0.72, lx, y + h], fill=RULE, width=6)
    if occupied:
        d.rounded_rectangle([x + w * 0.24, y + h * 0.16,
                             x + w * 0.86, y + h * 0.36],
                            radius=12, fill=(206, 216, 224))


def screen(d, x, y, w, h, title_txt, body_txt=None, accent=VERIFY):
    """一块屏。"""
    box(d, x, y, w, h, fill=PANEL, outline=RULE, width=3, r=12)
    d.rounded_rectangle([x, y, x + w, y + 46], radius=12, fill=accent)
    d.rectangle([x, y + 30, x + w, y + 46], fill=accent)
    t(d, x + 18, y + 11, title_txt, 24, True, PANEL)
    if body_txt:
        para_lines = body_txt.split("\n")
        for i, ln in enumerate(para_lines):
            t(d, x + 18, y + 66 + i * 40, ln, 25, False, INK2)
    d.rounded_rectangle([x + w * 0.34, y + h, x + w * 0.66, y + h + 16],
                        radius=6, fill=RULE)


def alert_card(d, x, y, w, h, real):
    """一条告警。real=True 画成砖红实心（真阳），否则灰框（假阳）。"""
    if real:
        box(d, x, y, w, h, fill=WRONG, outline=WRONG, width=2, r=6)
    else:
        box(d, x, y, w, h, fill=(236, 239, 241), outline=RULE, width=2, r=6)


def stat(d, x, y, num, label, col=INK, nsize=58, lsize=23, maxw=430):
    """label 里的 \n 是手工断行——数字和单位不能被自动换行拆开。"""
    d.text((x, y), num, font=f(nsize, True), fill=col)
    lines = []
    for seg in label.split("\n"):
        lines += wrap(d, seg, f(lsize), maxw)
    for i, ln in enumerate(lines):
        t(d, x, y + nsize + 12 + i * (lsize + 10), ln, lsize, False, MUTED)


def source(d, txt, w=W, h=HS):
    """右下角出处。场景图都基于真实案例，所以标出处而不是盖教学戳。"""
    ft = f(21)
    tw = d.textlength(txt, font=ft)
    d.text((w - PAD - tw, h - PAD - 24), txt, font=ft, fill=MUTED)


def scene_title(d, s, sub):
    t(d, PAD, 34, s, 42, True, INK)
    t(d, PAD, 92, sub, 26, False, MUTED)
    d.line([PAD, 142, W - PAD, 142], fill=RULE, width=3)


# ══════════════════════════════════════════════════════════════
# 场景一 · 病房：告警比病人多
# 对应上册第 13 章 Epic 败血症预测模型。这张图要让人一眼看到的是
# 「八个格子里只有一个是真的」——那比 PPV 0.12 这个数字直观得多。
# ══════════════════════════════════════════════════════════════
def ward():
    img, d = new(W, HS)
    scene_title(d, "病房里，告警比病人多",
                "一个被数百家医院采用的败血症预测模型，在一所大学医院 38,455 次住院上跑出来的样子")

    # 左：病房
    box(d, PAD, 176, 660, 350, fill=PANEL, outline=RULE, width=2, r=12)
    for i in range(3):
        bed(d, PAD + 28, 206 + i * 108, 236, 92)
    person(d, 618, 500, 128, INK2)
    t(d, PAD + 300, 210, "38,455 次住院", 28, True, INK)
    t(d, PAD + 300, 252, "其中 2,552 次", 24, False, MUTED)
    t(d, PAD + 300, 286, "发生败血症，占 7%", 24, False, MUTED)

    d.line([740, 350, 796, 350], fill=RULE, width=5)
    d.polygon([(796, 340), (816, 350), (796, 360)], fill=RULE)

    # 中：模型
    screen(d, 840, 200, 420, 214, "败血症风险预警",
           "评分 ≥ 6 时报警\n覆盖 18% 的住院\n（6,971 / 38,455）")

    d.line([1288, 350, 1344, 350], fill=RULE, width=5)
    d.polygon([(1344, 340), (1364, 350), (1344, 360)], fill=RULE)

    # 右：告警串
    t(d, 1390, 182, "阈值 ≥ 6 时，看八条告警才找出一例真的", 27, True, INK)
    for i in range(8):
        alert_card(d, 1390 + i * 116, 226, 98, 98, real=(i == 5))
    t(d, 1390, 344, "灰＝假阳性　　红＝真的败血症", 23, False, MUTED)

    # 右下：漏掉的那些
    box(d, 1390, 392, 914, 134, fill=WTINT, outline=WRONG, width=3, r=10)
    t(d, 1414, 414, "同时，模型没有识别出的败血症患者", 24, False, INK2)
    d.text((1414, 452), "1,709 人", font=f(46, True), fill=WRONG)
    t(d, 1614, 464, "占全部败血症病例的 67%", 26, True, WRONG)

    # 下：三个数字
    d.line([PAD, 610, W - PAD, 610], fill=RULE, width=3)
    stat(d, PAD, 650, "0.63", "独立外部验证的 AUROC\n厂商与合作医院联合报告为 0.76–0.83", INK, 62, 23, 760)
    stat(d, 900, 650, "12%", "阳性预测值\n报十次，一次多一点是真的", WRONG, 62, 23, 620)
    stat(d, 1660, 650, "33%", "灵敏度\n换一家医院、换一批患者，指标就掉下来", CAVEAT, 62, 23, 660)

    source(d, "Wong 等，JAMA Internal Medicine 2021;181(8):1065–1070")
    img.save(OUT / "scene-ward.png")
    return "scene-ward.png"




# ══════════════════════════════════════════════════════════════
# 场景二 · 政务大厅：门开着，人从旁边走
# 对应上册第 15 章 GOV.UK Verify。这张图的重点是右边那排方块——
# 十九项接入服务里有十一项另有入口，「绕过」不是态度问题，是路本来就有。
# ══════════════════════════════════════════════════════════════
def bypass():
    img, d = new(W, HS)
    scene_title(d, "门开着，人从旁边走",
                "一个全国统一身份认证平台：技术上完全达标，收益取决于有多少人注册")

    # 左：目标 vs 实际
    box(d, PAD, 176, 560, 352, fill=PANEL, outline=RULE, width=2, r=12)
    t(d, PAD + 26, 200, "2016 年商业论证定的目标", 24, True, MUTED)
    for i, (tgt, act, lbl) in enumerate([
            ("2,500 万", "360 万", "注册用户（2020 年）"),
            ("46 项", "19 项", "接入政府服务（2018-03 前）")]):
        y = 246 + i * 128
        d.text((PAD + 26, y), tgt, font=f(40, True), fill=MUTED)
        t(d, PAD + 250, y + 14, "→", 34, True, RULE)
        d.text((PAD + 310, y), act, font=f(40, True), fill=WRONG)
        t(d, PAD + 26, y + 58, lbl, 23, False, MUTED)

    # 中：一道门
    box(d, 700, 214, 220, 250, fill=PANEL, outline=VERIFY, width=4, r=12)
    d.rounded_rectangle([740, 254, 880, 464], radius=8, fill=TINT, outline=VERIFY, width=3)
    d.ellipse([856, 350, 872, 366], fill=VERIFY)
    t(d, 700, 176, "统一登录入口", 25, True, VERIFY)
    t(d, 700, 480, "技术上「完全符合规格」", 22, False, MUTED)

    # 绕行的人
    person(d, 985, 300, 104, MUTED)
    d.line([1030, 300, 1120, 300], fill=MUTED, width=5)
    d.polygon([(1120, 290), (1142, 300), (1120, 310)], fill=MUTED)
    t(d, 960, 320, "绕过去", 24, True, MUTED)

    # 右：19 项服务，11 项另有入口
    t(d, 1180, 176, "19 项接入服务里，至少 11 项另有入口", 27, True, INK)
    for i in range(19):
        cx, cy = 1180 + (i % 10) * 112, 220 + (i // 10) * 112
        other = i < 11
        box(d, cx, cy, 96, 96,
            fill=WTINT if other else TINT,
            outline=WRONG if other else VERIFY, width=3, r=8)
        if other:
            d.line([cx + 26, cy + 48, cx + 70, cy + 48], fill=WRONG, width=5)
    t(d, 1180, 452, "红＝用户还能从别的系统进　　青＝只能走这里", 23, False, MUTED)

    # 下
    d.line([PAD, 566, W - PAD, 566], fill=RULE, width=3)
    box(d, PAD, 596, 1180, 230, fill=TINT, outline=VERIFY, width=3, r=12)
    t(d, PAD + 26, 620, "政府项目管理局 2017 年的评估，被审计报告逐字收录：", 23, False, MUTED)
    for i, ln in enumerate(["「技术上是成功的、完全符合规格，", "但没有产生承诺的收益，", "因为收益取决于有多少人注册。」"]):
        t(d, PAD + 26, 662 + i * 46, ln, 30, True, INK)
    stat(d, 1300, 620, "670 万", "英镑：税务部门支付的使用费\n其他部门三年一家没付过，尽管发票已开", INK, 58, 23, 620)
    stat(d, 1960, 620, "8.73→2.17", "亿英镑：预计收益下修幅度", WRONG, 46, 23, 400)

    source(d, "英国国家审计署《Investigation into Verify》HC 1926，2019-03-05")
    img.save(OUT / "scene-bypass.png")
    return "scene-bypass.png"


# ══════════════════════════════════════════════════════════════
# 场景三 · 边检口：新的没建成，旧的还得养着
# 对应上册第 12 章 e-borders。这张图只讲一件事：两条线并行付钱，
# 而下面那条不进项目账——它记在运维预算里，复盘时看不见。
# ══════════════════════════════════════════════════════════════
def twobills():
    img, d = new(W, HS)
    scene_title(d, "新的没建成，旧的还得继续花钱养着",
                "一个要替换掉一批遗留系统的边境数据计划：立项时只算了上面那条线的钱")

    x0, x1 = PAD + 30, W - PAD - 30
    # 上：新系统
    t(d, x0, 190, "新系统（在建）", 26, True, VERIFY)
    d.rounded_rectangle([x0, 232, x1 - 420, 322], radius=10,
                        fill=TINT, outline=VERIFY, width=3)
    t(d, x0 + 24, 258, "统一出入境数据系统", 30, True, INK)
    d.rounded_rectangle([x1 - 400, 232, x1, 322], radius=10,
                        fill=GROUND, outline=RULE, width=3)
    t(d, x1 - 376, 258, "到审计时仍未建成", 28, True, MUTED)
    d.text((x0 + 24, 336), "£830m", font=f(52, True), fill=INK)
    t(d, x0 + 250, 356, "2006-04 至 2015-03 的投入", 24, False, MUTED)

    # 中：原定替换时点
    d.line([x0, 440, x1, 440], fill=RULE, width=3)
    box(d, 980, 408, 440, 66, fill=CTINT, outline=CAVEAT, width=3, r=8)
    t(d, 1004, 424, "原定 2011-04 完成替换", 27, True, CAVEAT)

    # 下：旧系统
    t(d, x0, 500, "旧系统（本该被替换掉）", 26, True, WRONG)
    d.rounded_rectangle([x0, 542, x1, 632], radius=10,
                        fill=WTINT, outline=WRONG, width=3)
    t(d, x0 + 24, 568, "遗留系统 —— 审计时仍在使用，而且一直在花钱改进", 30, True, INK)
    d.text((x0 + 24, 646), "£89m", font=f(52, True), fill=WRONG)
    t(d, x0 + 220, 666, "2011-04 以来投入到「本该被它替换掉的那些系统」上的改进费用",
      24, False, MUTED)

    # 下：两个佐证
    d.line([PAD, 736, W - PAD, 736], fill=RULE, width=3)
    stat(d, PAD, 768, "8", "位项目总监（2003–2015）", MUTED, 52, 23, 400)
    stat(d, 520, 768, "10 / 13", "份外部评审给出红色或琥珀红", CAVEAT, 52, 23, 460)
    box(d, 1080, 760, 1224, 108, fill=PANEL, outline=RULE, width=2, r=10)
    t(d, 1104, 778, "立项时值得多问一句：", 23, False, MUTED)
    t(d, 1104, 814, "如果这套东西晚一年，旧的那套要多花多少钱养着？", 27, True, INK)

    source(d, "英国国家审计署《E-borders and successor programmes》HC 608，2015-12")
    img.save(OUT / "scene-twobills.png")
    return "scene-twobills.png"


# ══════════════════════════════════════════════════════════════
# 场景四 · 放榜日：算法没算错，它精确地达成了被要求达成的目标
# 对应上册第 10 章「第六个问题：这是谁的目标」。
# 左右两栏是同一套算法的两种看法——机构看分布，学生看自己那一格。
# ══════════════════════════════════════════════════════════════
def whosegoal():
    img, d = new(W, HS)
    scene_title(d, "算法没算错，它精确地达成了被要求达成的那个目标",
                "考试取消后用算法定成绩：以教师预估为基础，参照这所学校前几年的成绩分布做调整")

    mid = W // 2
    d.line([mid, 176, mid, 700], fill=RULE, width=3)

    # 左：机构目标 —— 全国分布稳住了
    t(d, PAD, 186, "委托方的目标", 25, True, MUTED)
    t(d, PAD, 224, "防止全国成绩通胀", 36, True, INK)
    bx, by, bw = PAD + 20, 300, 130
    for i, h in enumerate([70, 140, 210, 250, 190, 110, 60]):
        d.rounded_rectangle([bx + i * bw, by + 260 - h, bx + i * bw + bw - 22, by + 260],
                            radius=6, fill=TINT, outline=VERIFY, width=3)
    t(d, PAD + 20, 584, "全国分布和往年一致 —— 这个目标达成了", 26, True, VERIFY)

    # 右：个体目标 —— 我这一次考得怎么样
    t(d, mid + 60, 186, "使用者的目标", 25, True, MUTED)
    t(d, mid + 60, 224, "我这一次考得怎么样", 36, True, INK)
    box(d, mid + 60, 300, 980, 240, fill=PANEL, outline=RULE, width=3, r=12)
    t(d, mid + 90, 326, "教师预估", 24, False, MUTED)
    d.text((mid + 90, 360), "A", font=f(76, True), fill=MUTED)
    t(d, mid + 210, 392, "→", 44, True, RULE)
    t(d, mid + 300, 326, "算法给出", 24, False, MUTED)
    d.text((mid + 300, 360), "C", font=f(76, True), fill=WRONG)
    box(d, mid + 430, 350, 570, 130, fill=WTINT, outline=WRONG, width=3, r=8)
    t(d, mid + 454, 370, "下调的依据不是他自己考得怎么样，", 24, False, INK2)
    t(d, mid + 454, 406, "是这所学校前几年考得怎么样。", 26, True, WRONG)
    t(d, mid + 60, 584, "两个目标在这件事上是冲突的，而冲突没有被当成问题", 26, True, WRONG)

    # 下
    d.line([PAD, 700, W - PAD, 700], fill=RULE, width=3)
    stat(d, PAD, 730, "39%", "教师预估成绩被算法下调", WRONG, 58, 23, 420)
    stat(d, 660, 730, "28 万", "份成绩受影响", WRONG, 58, 23, 360)
    stat(d, 1180, 730, "2 天", "从「结果可靠、可信」到改用教师预估", CAVEAT, 58, 23, 480)
    stat(d, 1800, 730, "2 位", "负责人相继辞职：考试监管机构、教育部常务次官", MUTED, 58, 23, 520)

    source(d, "多来源交叉核对，未取监管机构官方报告原文")
    img.save(OUT / "scene-whosegoal.png")
    return "scene-whosegoal.png"


ALL = ["ward", "bypass", "twobills", "whosegoal"]

if __name__ == "__main__":
    import sys
    for name in (sys.argv[1:] or ALL):
        print("✔", globals()[name]())
