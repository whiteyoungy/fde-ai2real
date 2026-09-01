#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""生成 Lab-01 的发票 PDF 夹具。

10 份样例：7 份可解析但脏、3 份破损。
每一份都对应现场真实遇到过的一类问题，不是格式整齐的假样本。

用法：python3 fixtures/generate.py
产出：fixtures/pdfs/*.pdf + fixtures/expected/manifest.json
"""
import json
import pathlib
import random

import fitz  # PyMuPDF

BASE = pathlib.Path(__file__).parent
PDF_DIR = BASE / "pdfs"
EXP_DIR = BASE / "expected"

# 用系统里确定存在的 CJK 字体，避免字形缺失导致"假破损"
CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"


def _page(doc, lines, fontsize=11, start=(60, 70), leading=20, font=None):
    """把 (x_offset, text) 列表画到新页上。"""
    page = doc.new_page()
    fname = None
    if font:
        fname = page.insert_font(fontname="cjk", fontfile=font)
    y = start[1]
    for item in lines:
        if item is None:
            y += leading
            continue
        dx, text = item if isinstance(item, tuple) else (0, item)
        page.insert_text(
            (start[0] + dx, y), text,
            fontsize=fontsize,
            fontname="cjk" if fname else "helv",
        )
        y += leading
    return page


def make(name, lines, **kw):
    doc = fitz.open()
    _page(doc, lines, font=CJK_FONT, **kw)
    path = PDF_DIR / name
    doc.save(path)
    doc.close()
    return path


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(20260808)
    manifest = []

    # ── 1. 基线：字段齐整，最容易的一份 ────────────────────────────
    make("inv-01-baseline.pdf", [
        "增值税专用发票",
        None,
        "发票号码：INV-2026-000101",
        "开票日期：2026-03-05",
        "购买方：晟远精密制造有限公司",
        "纳税人识别号：91310000MA1FL0XY3K",
        "金额（不含税）：12500.00",
        "税率：13%",
        "税额：1625.00",
        "价税合计：14125.00",
    ])
    manifest.append(dict(
        file="inv-01-baseline.pdf", outcome="pass",
        expect=dict(invoice_no="INV-2026-000101", invoice_date="2026-03-05",
                    amount_excl_tax=12500.00, tax_amount=1625.00, total=14125.00),
        dirt="无。基线用例，用来确认管道本身通路正常。",
    ))

    # ── 2. 字段顺序不同 + 日期格式不同 ─────────────────────────────
    make("inv-02-field-order.pdf", [
        "INVOICE / 发 票",
        None,
        "购买方        海临自动化设备（苏州）有限公司",
        "价税合计      8,832.00",
        "税额          1,016.00",
        "金额          7,816.00",
        "税率          13%",
        "开票日期      2026/03/11",
        "发票号码      INV-2026-000102",
    ])
    manifest.append(dict(
        file="inv-02-field-order.pdf", outcome="pass",
        expect=dict(invoice_no="INV-2026-000102", invoice_date="2026-03-11",
                    amount_excl_tax=7816.00, tax_amount=1016.00, total=8832.00),
        dirt="字段顺序与基线完全不同；日期用 2026/03/11 斜杠格式；金额带千分位逗号。",
    ))

    # ── 3. 表格式版式：标签与值分列，靠 x 坐标对齐 ──────────────────
    make("inv-03-table-layout.pdf", [
        "                    电 子 发 票",
        None,
        (0, "项目"), (200, "规格"), (300, "数量"), (380, "单价"), (460, "金额"),
        None,
        (0, "冲压件 A-77"), (200, "Q235"), (300, "1200"), (380, "3.20"), (460, "3840.00"),
        (0, "冲压件 B-12"), (200, "Q235"), (300, "800"), (380, "2.95"), (460, "2360.00"),
        None,
        (0, "发票号码 INV-2026-000103    开票日期 2026-03-18"),
        (0, "合计金额 6200.00   税额 806.00   价税合计 7006.00"),
    ], fontsize=9, leading=16)
    manifest.append(dict(
        file="inv-03-table-layout.pdf", outcome="pass",
        expect=dict(invoice_no="INV-2026-000103", invoice_date="2026-03-18",
                    amount_excl_tax=6200.00, tax_amount=806.00, total=7006.00),
        dirt="表格版式，字段靠 x 坐标分列。纯按行取文本会把表头和数据混在一行。",
    ))

    # ── 4. 关键字段跨行断开 ────────────────────────────────────────
    make("inv-04-wrapped-field.pdf", [
        "增值税普通发票",
        None,
        "发票号码：INV-2026-",
        "000104",
        "开票日期：2026 年 03 月",
        "23 日",
        "购买方：北方重工机械（沈阳）",
        "有限责任公司",
        "金额：15,600.00   税额：2,028.00",
        "价税合计：17,628.00",
    ])
    manifest.append(dict(
        file="inv-04-wrapped-field.pdf", outcome="pass",
        expect=dict(invoice_no="INV-2026-000104", invoice_date="2026-03-23",
                    amount_excl_tax=15600.00, tax_amount=2028.00, total=17628.00),
        dirt="发票号码与日期都被换行截断。中文日期格式「2026 年 03 月 23 日」跨两行。",
    ))

    # ── 5. 全角数字 + 中英混排 ─────────────────────────────────────
    make("inv-05-fullwidth.pdf", [
        "Commercial Invoice / 商业发票",
        None,
        "Invoice No.  ＩＮＶ－２０２６－０００１０５",
        "Date         ２０２６－０４－０２",
        "Buyer        Kunlun Precision Co., Ltd. 昆仑精密",
        "Net Amount   ９，８００．００",
        "Tax (13%)    １，２７４．００",
        "Gross Total  １１，０７４．００",
    ])
    manifest.append(dict(
        file="inv-05-fullwidth.pdf", outcome="pass",
        expect=dict(invoice_no="INV-2026-000105", invoice_date="2026-04-02",
                    amount_excl_tax=9800.00, tax_amount=1274.00, total=11074.00),
        dirt="全角数字与全角标点。不做 NFKC 归一化会解析成乱码或抽不到数字。",
    ))

    # ── 6. 缺可选字段 + 多出无关字段 ───────────────────────────────
    make("inv-06-missing-optional.pdf", [
        "收 款 收 据",
        None,
        "单据编号：INV-2026-000106",
        "日期：2026-04-15",
        "付款方：individual（个人，无纳税人识别号）",
        "备注：本单为预付款，尾款另开",
        "经办人：张伟    审核人：李娜",
        "合计：3,000.00",
        "（本单据不含税，无税额栏）",
    ])
    manifest.append(dict(
        file="inv-06-missing-optional.pdf", outcome="pass",
        expect=dict(invoice_no="INV-2026-000106", invoice_date="2026-04-15",
                    amount_excl_tax=3000.00, tax_amount=0.00, total=3000.00),
        dirt="无税额栏、无纳税人识别号；多出经办人/审核人等无关字段。"
             "校验层要能接受 tax_amount=0 且不被无关字段带偏。",
    ))

    # ── 7. 红字发票：负数金额 ──────────────────────────────────────
    make("inv-07-credit-note.pdf", [
        "增值税专用发票（红字）",
        None,
        "发票号码：INV-2026-000107",
        "开票日期：2026-04-28",
        "购买方：晟远精密制造有限公司",
        "对应蓝字发票号：INV-2026-000101",
        "金额：-12,500.00",
        "税额：-1,625.00",
        "价税合计：-14,125.00",
        "（红字冲销，金额为负）",
    ])
    manifest.append(dict(
        file="inv-07-credit-note.pdf", outcome="pass",
        expect=dict(invoice_no="INV-2026-000107", invoice_date="2026-04-28",
                    amount_excl_tax=-12500.00, tax_amount=-1625.00, total=-14125.00),
        dirt="红字发票金额为负。若校验层写死 amount > 0 会误判为脏数据。",
    ))

    # ── 8. 破损：文件被截断 ────────────────────────────────────────
    src = make("_tmp-truncate.pdf", ["增值税专用发票", "发票号码：INV-2026-000108"])
    raw = src.read_bytes()
    (PDF_DIR / "bad-08-truncated.pdf").write_bytes(raw[: int(len(raw) * 0.55)])
    src.unlink()
    manifest.append(dict(
        file="bad-08-truncated.pdf", outcome="quarantine",
        reason="文件被截断，PDF 结构不完整，解析器应抛异常而非返回半份数据",
        dirt="传输中断/磁盘写坏的典型形态。",
    ))

    # ── 9. 破损：扫描件，无文本层 ──────────────────────────────────
    doc = fitz.open()
    page = doc.new_page()
    # 画矩形与线条模拟扫描件版面，但不插入任何文本
    page.draw_rect(fitz.Rect(50, 50, 545, 120), color=(0.2, 0.2, 0.2), width=1.2)
    for i in range(8):
        y = 150 + i * 26
        page.draw_line(fitz.Point(60, y), fitz.Point(300 + (i * 17) % 220, y),
                       color=(0.35, 0.35, 0.35), width=2.4)
    page.draw_rect(fitz.Rect(380, 300, 540, 380), color=(0.5, 0.1, 0.1), width=2)
    doc.save(PDF_DIR / "bad-09-scanned-no-text.pdf")
    doc.close()
    manifest.append(dict(
        file="bad-09-scanned-no-text.pdf", outcome="quarantine",
        reason="无文本层（扫描件），文本抽取返回空，不应交给模型硬猜",
        dirt="纯图像发票。没有 OCR 环节时必须识别出「抽不到文本」并隔离，"
             "而不是把空字符串喂给模型让它编。",
    ))

    # ── 10. 破损：有文本但关键字段缺失 ─────────────────────────────
    make("bad-10-missing-critical.pdf", [
        "增值税专用发票",
        None,
        "购买方：未知单位",
        "开票日期：2026-05-",          # 日期不完整
        "备注：此页为发票第二联，金额栏在第一联",
        "经办人：王强",
        "（本页无发票号码与金额）",
    ])
    manifest.append(dict(
        file="bad-10-missing-critical.pdf", outcome="quarantine",
        reason="缺发票号码与金额，日期不完整；强类型校验必须失败且自纠错也补不出来",
        dirt="多联发票只扫了一联。模型很容易在这里编一个号码和金额出来——"
             "这正是本 Lab 要防的：校验层挡住，自纠错若干轮后仍失败则进隔离队列。",
    ))

    (EXP_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    n_pass = sum(1 for m in manifest if m["outcome"] == "pass")
    n_quar = sum(1 for m in manifest if m["outcome"] == "quarantine")
    print(f"生成 {len(manifest)} 份夹具：{n_pass} 份应解析成功，{n_quar} 份应进隔离队列")
    for m in manifest:
        print(f"  [{m['outcome']:<10}] {m['file']}")


if __name__ == "__main__":
    main()
