#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""显存预算表生成器（讲义第 23 章）。

这张表要回答的不是"这个模型多大"，而是"我该给它配多大的卡"。这两个是
不同的数字，中间差一个上浮系数，而这个系数正是现场最容易被省掉的一步。

两件事必须在表里分开写清楚：

1. **口径**：每个数字是**官方给出**的部署显存要求，还是**按参数量估算**
   出来的。这两者的可信度差着一个数量级——官方数字通常已经包含了推理
   框架的实际开销，估算值只是"参数量 × 每参数字节数"，只含权重。
   把估算值当官方值用，是"看起来有数据支撑"的错觉。

2. **上浮**：估算值必须按 **≥20%** 上浮后才能作为配置依据。理由不是
   拍脑袋——估算值不含 KV Cache，而 KV Cache 随并发数和上下文长度线性
   增长，贴着估算值配硬件在真实负载下必然 OOM。第 23 章原文要求
   "不低于 20%"。**20% 是地板不是目标**：长上下文或高并发场景要按
   本文给出的 KV Cache 公式实算，往往远不止 20%。

用法：
    python3 -m src.vram_budget --models fixtures/models.json --out results

产出 ``results/vram_budget.md``。
"""
import argparse
import json
import math
import pathlib
import sys

# 第 23 章要求的最低上浮比例。改小它就是在给未来的 OOM 埋雷。
HEADROOM = 1.20

# 常见单卡显存档位（GB）。用于把上浮后的数字落到"实际买得到的东西"上——
# 17GB 这个数字没法下单，得说成"一张 24GB 卡"。
CARD_SIZES = [4, 8, 12, 16, 24, 32, 40, 48, 80, 96, 141]
MULTI_CARD_UNIT = 80  # 超过最大单卡档位时，按 80GB 卡计张数


def recommend(need_gb: float) -> str:
    """把上浮后的显存需求落到可采购的硬件形态上。"""
    for size in CARD_SIZES:
        if need_gb <= size:
            return f"单卡 {size}GB"
    cards = math.ceil(need_gb / MULTI_CARD_UNIT)
    nodes = math.ceil(cards / 8)
    node_desc = "单机 8 卡即可" if nodes <= 1 else f"需 {nodes} 台 8 卡整机，跨机互联"
    return f"{cards} × {MULTI_CARD_UNIT}GB（{node_desc}）"


def render(models: list) -> str:
    official = [m for m in models if m["vram_gb"]["basis"] != "估算"]
    estimated = [m for m in models if m["vram_gb"]["basis"] == "估算"]

    lines = [
        "# 显存预算表",
        "",
        "本表由 `python3 -m src.vram_budget` 从 `fixtures/models.json` 生成。",
        "",
        "## 先看口径：两列数字的可信度不一样",
        "",
        "| 口径 | 含义 | 可信度 | 该怎么用 |",
        "|---|---|---|---|",
        "| **官方给出** | 模型方在部署文档里写明的显存要求 | 高。通常已包含推理框架的实际开销 |"
        " 可直接作为配置下限参考，仍建议留余量 |",
        "| **按参数量估算** | 参数量 × 每参数字节数（BF16 为 2 字节）算出来的权重体积 |"
        " 低。**只含权重**，不含 KV Cache、激活值、框架开销、显存碎片 |"
        " **必须按 ≥20% 上浮后**才能作为配置依据 |",
        "",
        f"本表 {len(models)} 个档位中，**官方给出** {len(official)} 个、"
        f"**按参数量估算** {len(estimated)} 个。",
    ]
    if not official:
        lines += [
            "",
            "> 注意：本快照里**没有任何一行是官方给出的口径**，全部是按参数量估算。",
            "> 这不是疏忽，而是如实反映取数状态——正式选型时应回到各模型官方仓库",
            "> 的部署文档，把能拿到官方显存要求的行替换掉，并在表里改标口径。",
            "> 在替换之前，下面每一行的建议值都只能当作量级参考，不能当作采购依据。",
        ]

    lines += [
        "",
        "## 预算表",
        "",
        "| 档位 | id | 口径 | 原始数字 (GB) | ×1.2 上浮后 (GB) | 建议配置值 | 上浮理由 |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in models:
        v = float(m["vram_gb"]["value"])
        basis = m["vram_gb"]["basis"]
        note = m["vram_gb"].get("note", "")
        if basis == "估算":
            need = v * HEADROOM
            basis_label = "按参数量估算"
            reason = "估算值只算权重、不含 KV Cache，贴着它配必 OOM"
            uplift = f"{need:.1f}"
            rec = recommend(need)
        else:
            need = v
            basis_label = "官方给出"
            reason = "官方口径已含框架开销，按官方值配置并自行留并发余量"
            uplift = "—（官方口径不适用本上浮规则）"
            rec = recommend(v)
        lines.append(
            f"| {m['name']} | `{m['id']}` | {basis_label} | {v:g} | {uplift} | "
            f"{rec} | {reason}；{note} |")

    lines += [
        "",
        "> 表中「×1.2 上浮后」一列是**计算值**，「建议配置值」是把它落到实际",
        "> 可采购硬件档位后的结果（向上取整到常见单卡规格；超过最大单卡档位时",
        "> 按 80GB 卡折算张数）。两个数字都给，是因为前者可复核、后者可下单。",
        "",
        "## 20% 这个比例是怎么来的，以及它为什么是地板",
        "",
        "估算值 = 参数量 × 每参数字节数。BF16 每参数 2 字节，所以 7B 约 14GB。",
        "这个数字**只包含权重**，推理时真正占显存的还有：",
        "",
        "1. **KV Cache** —— 最大的一块，且随并发数与上下文长度**线性增长**。",
        "2. **激活值** —— 前向计算的中间张量，随 batch 增长。",
        "3. **推理框架开销** —— CUDA context、通信缓冲区、算子工作区。",
        "4. **显存碎片** —— 变长请求反复申请释放造成，长跑服务尤其明显。",
        "",
        "20% 是覆盖 3、4 两项并给 1、2 留一点起步空间的经验下限，",
        "**不是「加了 20% 就够用」的许可**。KV Cache 该实算：",
        "",
        "```",
        "KV Cache 字节数 ≈ 2 × 层数 × KV 头数 × 每头维度 × 序列长度 × 并发数 × 每元素字节数",
        "```",
        "",
        "式中「2」是 K 和 V 两份。层数、KV 头数、每头维度请从该模型官方仓库的",
        "`config.json` 里取（`num_hidden_layers` / `num_key_value_heads` /",
        "`hidden_size ÷ num_attention_heads`），**不要凭印象填**——不同档位之间",
        "这几个数不是等比缩放的，GQA 的 KV 头数尤其容易估错。本表刻意不替各档位",
        "代入这些参数，因为 `fixtures/models.json` 里没有这些字段，编一组出来",
        "会让整张表看起来比它实际的可信度更高。",
        "",
        "实际做法：拿客户的目标并发与目标上下文代入上式，加到权重体积上，",
        "再取「该结果」与「权重 × 1.2」中的较大者作为配置依据。长上下文",
        "（128K）或高并发场景下，KV Cache 常常比权重本身还大，20% 远远不够。",
        "",
        "## 一处必须如实记下的口径不一致",
        "",
        "`fixtures/models.json` 里，Qwen 三档的备注都写明了「BF16 权重约 XGB」，",
        "按 BF16 = 2 字节/参数可以自洽复核；但 `deepseek-v3` 那一行只写了",
        "「MoE 全量权重」，**没有写明按每参数几字节估算**。以 671B 总参数反推，",
        "700GB 对应的是约 1 字节/参数（FP8 量级），不是 BF16 的 2 字节",
        "（若按 BF16 应在 1.3TB 量级）。",
        "",
        "本表不替它改数、也不替它补一个精度口径——这一行的原始依据在夹具里就",
        "是缺的，补一个看起来合理的口径只会掩盖缺口。使用这一行之前，必须回到",
        "DeepSeek 官方仓库确认权重的实际存储精度与文件总体积，再决定按哪个口径",
        "折算。**这一行的 840GB 只能当作「单机放不下」这个量级判断的依据，",
        "不能当作采购数字。**",
        "",
        "## 使用这张表之前必须做的两件事",
        "",
        "1. **重新取数**。许可证条款、上下文长度、显存要求都会变。",
        "   `fixtures/models.json` 是写作时的快照，正式项目里必须从各模型官方",
        "   仓库的 LICENSE 与 `config.json` 重新取数，并标注取数日期。",
        "2. **实测验证**。配置值定下来之后，用客户的真实并发与真实文档长度",
        "   压一遍，看显存峰值。表算出来的是起点，不是结论。",
        "",
        "## 一个不在显存表里、但会先卡住你的约束",
        "",
        "显存算得再准，也拦不住许可证问题。本表里显存最省的几档中，",
        "`qwen2.5-3b-instruct` 用的是 Qwen RESEARCH LICENSE AGREEMENT，",
        "**不可商用**。选型的第一步是商用授权，不是显存——顺序见 `src/select.py`。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成显存预算表")
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)

    models = json.loads(pathlib.Path(args.models).read_text(encoding="utf-8"))["models"]
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "vram_budget.md"
    dest.write_text(render(models), encoding="utf-8")
    print(f"written={dest}（{len(models)} 个档位）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
