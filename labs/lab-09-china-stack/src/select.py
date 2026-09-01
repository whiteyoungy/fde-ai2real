#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""国产栈五步判据选型（讲义第 23 章）。

五步判据，**顺序不能换**：

    1. 商用授权 → 2. 显存预算 → 3. 上下文需求 → 4. 函数调用 → 5. 中文能力

把商用授权放在第一步，不是因为它最容易判，而是因为它是这五步里唯一一个
"过不了就完全出局、再好的技术指标也救不回来"的维度。后面四步都是程度
问题——显存不够可以加卡、上下文不够可以分块、函数调用不支持可以外挂
一层解析、中文一般可以加提示词。只有许可证不是程度问题：Qwen2.5-3B-Instruct
用的是 Qwen RESEARCH LICENSE AGREEMENT，仅限研究与评估，不可商用；而同系列
的 72B 用的是允许商用的 Qwen License。**档位相邻不代表授权条款相邻。**

这个坑之所以危险，是因为它和所有技术直觉都反着来：3B 参数最小、显存最省、
在资源受限的现场看起来最合适——恰恰是它不能商用。选错的代价不是效果差
一点，是项目上线后被法务叫停。夹具里的 s1/s2 是同一套硬件约束、只差
"是否商用"一个条件，正确答案就换了一档，就是为了把这件事演出来。

用法：
    python3 -m src.select --models fixtures/models.json \\
        --scenarios fixtures/scenarios.json --out results

产出 ``results/selection.json``，每个场景一条记录：

- ``selected``：选中的模型 id；可行集为空时为 ``null``
- ``reason``：为什么是它 / 为什么没有
- ``funnel``：五步漏斗的逐步存活情况（每一步淘汰了谁、因为什么）
- ``negotiation``：**仅在可行集为空时出现**，给客户的谈判建议

关于 ``negotiation``：五步走完可行集为空，正确做法是回去和客户谈判放松
某个维度，不是硬凑一个方案上线。但只对客户说一句"无解"同样没有价值——
客户要的是一道选择题，不是一堵墙。所以这个字段必须写清楚：该放松哪个
维度、放松之后走什么替代路径、各自的代价是什么。

关于显存口径的一个刻意选择：这里的可行性过滤用夹具里的**原始**显存数字
（估算值只含权重、不含 KV Cache），而不是 vram_budget.py 里那个上浮 20%
后的配置值。理由是两者回答的是不同的问题——选型阶段问的是"这个档位在
这类硬件上是不是根本不成立"，配机阶段问的是"实际要买多大的卡才不会 OOM"。
把上浮值用在选型过滤上会让判据随上浮系数漂移，而上浮系数是个工程经验值。
两个口径在本 Lab 的四个场景上结论一致，但 reason 里会同时给出配置值，
免得下游拿原始值去配硬件。
"""
import argparse
import json
import pathlib
import sys

# 五步判据的顺序在这里固化。改这个列表的顺序 = 改判据顺序，
# verify.sh 第 3 项对此零容忍，不要"顺手优化"成先过滤显存再判许可证。
CRITERIA_ORDER = ["商用授权", "显存预算", "上下文需求", "函数调用", "中文能力"]

# 中文能力是有序枚举，不是自由文本。比较时转成序数。
CHINESE_RANK = {"弱": 0, "一般": 1, "较强": 2, "强": 3}

# 显存上浮系数：估算值只含权重、不含 KV Cache，贴着估算值配硬件在真实
# 负载下必然 OOM。第 23 章要求"不低于 20%"。这里只用于在 reason 里给出
# 配置建议值，不参与可行性过滤（见模块 docstring）。
VRAM_HEADROOM = 1.20


def _rank(level: str) -> int:
    """中文能力等级 → 序数。未知等级按最低处理（宁可漏选不可错选）。"""
    return CHINESE_RANK.get(str(level).strip(), 0)


def _vram(model: dict) -> float:
    return float(model["vram_gb"]["value"])


# ── 五步判据，每一步是一个 (名称, 谓词, 淘汰理由生成器) ──────────────
# 谓词签名统一为 (model, constraints) -> bool。


def _pass_license(m: dict, c: dict) -> bool:
    """第 1 步 · 商用授权（一票否决）。

    只有当客户明确要商用时才构成约束：场景说"只做内部研究评估、不上生产"
    时，研究许可档位是完全合法的选项，不该被排除。所以这一步不是
    "永远排除不可商用的模型"，而是"客户要商用时，不可商用的一律出局"。
    """
    if not c.get("commercial_use"):
        return True
    return bool(m.get("commercial_use"))


def _pass_vram(m: dict, c: dict) -> bool:
    """第 2 步 · 显存预算。上限缺省视为不设限。"""
    cap = c.get("vram_gb_max")
    return cap is None or _vram(m) <= float(cap)


def _pass_context(m: dict, c: dict) -> bool:
    """第 3 步 · 上下文需求。

    注意这里是"≥ 客户要求"的硬门槛，不是"在候选里取最大的"。
    把它写成"取最大"是 s3 会被硬凑出一个答案的典型原因。
    """
    need = c.get("context_min")
    return need is None or int(m.get("context", 0)) >= int(need)


def _pass_function_calling(m: dict, c: dict) -> bool:
    """第 4 步 · 函数调用。客户不要求时不构成约束。"""
    if not c.get("function_calling"):
        return True
    return bool(m.get("function_calling"))


def _pass_chinese(m: dict, c: dict) -> bool:
    """第 5 步 · 中文能力。"""
    need = c.get("chinese_min")
    return need is None or _rank(m.get("chinese")) >= _rank(need)


STEPS = [
    (CRITERIA_ORDER[0], _pass_license,
     lambda m, c: f"许可证 {m['license']}，不可商用"),
    (CRITERIA_ORDER[1], _pass_vram,
     lambda m, c: f"显存 {_vram(m):g}GB 超出预算 {c.get('vram_gb_max')}GB"),
    (CRITERIA_ORDER[2], _pass_context,
     lambda m, c: f"上下文 {m.get('context')} < 要求 {c.get('context_min')}"),
    (CRITERIA_ORDER[3], _pass_function_calling,
     lambda m, c: "不支持函数调用"),
    (CRITERIA_ORDER[4], _pass_chinese,
     lambda m, c: f"中文能力「{m.get('chinese')}」低于要求「{c.get('chinese_min')}」"),
]


def run_funnel(models: list, constraints: dict) -> tuple:
    """按固定顺序跑五步漏斗。

    返回 ``(survivors, funnel)``：``survivors`` 是可行集（模型 dict 列表），
    ``funnel`` 是逐步的审计记录——每一步存活几个、淘汰了谁、因为什么。

    漏斗记录不是装饰。选型结论要能对客户和法务复盘，"为什么 3B 没进最终
    名单"必须有一条能指着念的记录，而不是一个黑箱里出来的模型名。
    """
    survivors = list(models)
    funnel = []
    for idx, (name, predicate, why) in enumerate(STEPS, start=1):
        kept, dropped = [], []
        for m in survivors:
            if predicate(m, constraints):
                kept.append(m)
            else:
                dropped.append({"id": m["id"], "why": why(m, constraints)})
        funnel.append({
            "step": idx,
            "criterion": name,
            "survivors": [m["id"] for m in kept],
            "eliminated": dropped,
        })
        survivors = kept
    return survivors, funnel


def pick(survivors: list) -> dict:
    """在可行集里定选。

    可行集里的每一个都已经满足全部硬约束，此时的取舍原则是**够用就好**：
    优先显存占用最小的那一个。理由是现场部署里显存是最贵、最难追加的
    资源，同样满足需求时多占的每一 GB 都是白花的钱和更差的并发。

    显存相同时按 id 排序，保证结果可复现——选型脚本跑两次给出不同答案
    是没法向客户交代的。
    """
    return sorted(survivors, key=lambda m: (_vram(m), m["id"]))[0]


def _headroom_hint(model: dict) -> str:
    v = _vram(model)
    basis = model["vram_gb"]["basis"]
    if basis == "估算":
        return (f"显存 {v:g}GB（{basis}，只含权重不含 KV Cache），"
                f"实际配机按 ≥20% 上浮取 {v * VRAM_HEADROOM:.1f}GB")
    return f"显存 {v:g}GB（{basis}）"


def _relaxed_feasible(models: list, constraints: dict, skip_step: int) -> list:
    """把第 ``skip_step`` 步（1-based）这一维放松掉之后，谁能通过其余四步。

    这才是谈判建议里该报给客户的名单。直接报"进入卡点那一步时还活着的
    候选"是不对的——那些候选可能在后面的步骤上照样出局，报给客户等于
    给了一个跑不通的方案。
    """
    out = []
    for m in models:
        if all(pred(m, constraints)
               for idx, (_, pred, _) in enumerate(STEPS, start=1)
               if idx != skip_step):
            out.append(m)
    return sorted(out, key=lambda m: (_vram(m), m["id"]))


def _negotiation_advice(scenario: dict, models: list, funnel: list) -> str:
    """可行集为空时，生成给客户的谈判建议。

    生成逻辑不是套模板：先找出"是哪一步把最后的候选打光的"，再算出
    "把这一维放松掉之后谁真的能用"，最后针对性给出替代路径和代价。
    只说"无解"对客户没有价值——要给的是一道带代价标注的选择题。
    """
    c = scenario["constraints"]
    # 找出第一个存活者为空的步骤——就是把可行集打空的那一步。
    killer = next((f for f in funnel if not f["survivors"]), None)
    prev_alive = []
    for f in funnel:
        if f["survivors"]:
            prev_alive = f["survivors"]
        else:
            break
    if killer is None:
        return "可行集非空，无需谈判。"

    blocked = [d for d in killer["eliminated"]]
    crit = killer["criterion"]
    # 放松卡点这一维之后真正可用的名单（仍需通过其余四步）。
    relaxed = _relaxed_feasible(models, c, killer["step"])
    relaxed_ids = [m["id"] for m in relaxed]

    lines = [
        f"五步判据走到第 {killer['step']} 步「{crit}」时可行集被清空"
        f"（进入该步的候选：{'、'.join(prev_alive) or '无'}）。"
        f"此时不应硬凑一个勉强的方案上线，而应回到客户面前把约束摊开谈。"
    ]
    if blocked:
        lines.append("卡在这一步的候选及原因：" +
                     "；".join(f"{d['id']}（{d['why']}）" for d in blocked) + "。")

    # 针对具体的卡点给出可谈的两条路，并标出各自代价。
    if crit == "上下文需求":
        need = c.get("context_min")
        cap = c.get("vram_gb_max")
        # 谁是"只差显存"的那一个：满足上下文但显存超预算的模型。
        long_ctx = [m for m in models
                    if int(m.get("context", 0)) >= int(need)
                    and (not c.get("commercial_use") or m.get("commercial_use"))]
        long_ctx_desc = "、".join(
            f"{m['id']}（需 {_vram(m):g}GB，"
            f"按 ≥20% 上浮配机 {_vram(m) * VRAM_HEADROOM:.0f}GB，"
            f"远超单卡 {cap}GB 预算）" for m in long_ctx) or "无"
        lines.append(
            f"可谈的方向 A —— **放松上下文要求**：把「单次喂进 {need} token」"
            f"改为「32K 上下文 + 分块检索（RAG）」。长文档先切块、建索引，"
            f"每次只把命中的若干块喂给模型。放松这一维后仍能通过其余四步的"
            f"候选是 {'、'.join(relaxed_ids) or '无'}"
            f"{'（推荐 ' + relaxed_ids[0] + '）' if relaxed_ids else ''}，"
            f"硬件不用动。代价是要额外建一套检索与重排链路，"
            f"且跨块推理（例如「通篇比对前后条款是否矛盾」）的效果会下降，"
            f"需要在验收用例里单独把这类问题挑出来评测。这通常是性价比最高的一条。")
        lines.append(
            f"可谈的方向 B —— **放松硬件预算**：真要 {need} token 原生上下文，"
            f"当前满足条件的只有 {long_ctx_desc}，单卡放不下，"
            f"必须走多卡/多机分布式推理。代价是硬件采购与机房条件（供电、"
            f"散热、机柜位）都要重新评估，交付周期按季度计，且分布式推理的"
            f"运维复杂度远高于单机。若客户预算和周期允许，这条能拿到最好的效果。")
        lines.append(
            "可谈的方向 C —— **拆分场景**：把「长文档全文理解」和「日常问答」"
            "拆成两条链路，后者用单卡 32K 档位本地跑，前者走客户已合规备案的"
            "外部大上下文服务或离线批处理。代价是要多维护一条链路，"
            "且外部服务是否满足该客户的数据出域要求需要先过合规。")
    elif crit == "商用授权":
        lines.append(
            "可谈的方向 A —— **确认用途边界**：如果确实只做内部研究与评估、"
            "不进入生产、不对外提供服务，研究许可档位是合法可用的，"
            "但这个结论必须由客户法务出书面确认，不能由技术方口头判断。")
        lines.append(
            "可谈的方向 B —— **换用允许商用的档位**：同系列里许可证允许商用的"
            "档位往往参数量更大、显存要求更高，需要同步谈硬件预算。")
    elif crit == "显存预算":
        lines.append(
            "可谈的方向 A —— **加硬件预算或走多卡**：把显存上限抬到能装下"
            "最小可行档位的水平。代价是采购周期与机房条件。")
        lines.append(
            "可谈的方向 B —— **接受量化部署**：INT8/INT4 量化可把权重显存压到"
            "BF16 的 1/2–1/4。代价是效果有损，必须用客户自己的验收集实测"
            "量化前后的差距，不能拿公开榜单的结论替代。")
    else:
        lines.append(
            f"可谈的方向 —— **放松「{crit}」这一维**，或在应用层补齐该能力"
            f"（例如函数调用可用受限输出 + 解析层外挂，中文能力可用领域"
            f"提示词与少样本示例补齐）。代价都是工程量与稳定性，需要实测。")

    lines.append(
        "建议的推进方式：把上面几条做成一页纸的选择题交给客户决策人，"
        "每条标清「要放松什么、换来什么、代价是什么」，并注明技术方的推荐项"
        "与推荐理由。选型阶段的产出是一个决策，不是一个模型名。")
    return "".join(lines)


def select_for_scenario(scenario: dict, models: list) -> dict:
    sid = scenario["id"]
    constraints = scenario["constraints"]
    survivors, funnel = run_funnel(models, constraints)

    record = {
        "scenario_id": sid,
        "desc": scenario.get("desc", ""),
        "constraints": constraints,
        "criteria_order": CRITERIA_ORDER,
        "funnel": funnel,
        "feasible_set": [m["id"] for m in survivors],
    }

    if not survivors:
        record["selected"] = None
        record["reason"] = (
            f"五步判据走完可行集为空，不硬凑。清空发生在第 "
            f"{next(f['step'] for f in funnel if not f['survivors'])} 步"
            f"「{next(f['criterion'] for f in funnel if not f['survivors'])}」。"
            f"正确动作是回去和客户谈判放松某个维度，见 negotiation 字段。")
        record["negotiation"] = _negotiation_advice(scenario, models, funnel)
        return record

    chosen = pick(survivors)
    others = [m["id"] for m in survivors if m["id"] != chosen["id"]]
    reason_parts = [
        f"五步判据全部通过的可行集为 {{{'、'.join(record['feasible_set'])}}}；",
        f"在可行集内按「够用就好、显存最省」定选 {chosen['id']}"
        f"（{_headroom_hint(chosen)}）。",
    ]
    if others:
        reason_parts.append(
            f"同样可行但显存更高因而未选：{'、'.join(others)}。")
    # 把第一步淘汰了谁显式写进 reason——这是最需要能对法务复盘的一条。
    lic_out = funnel[0]["eliminated"]
    if lic_out:
        reason_parts.append(
            "第 1 步商用授权一票否决的档位：" +
            "；".join(f"{d['id']}（{d['why']}）" for d in lic_out) + "。")
    else:
        reason_parts.append(
            "本场景未要求商用（客户声明仅内部研究评估），"
            "第 1 步不构成约束，研究许可档位保留在候选内——"
            "这一结论应由客户法务书面确认后才可落地。")
    record["selected"] = chosen["id"]
    record["reason"] = "".join(reason_parts)
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="国产栈五步判据选型")
    ap.add_argument("--models", required=True, help="models.json 路径")
    ap.add_argument("--scenarios", required=True, help="scenarios.json 路径")
    ap.add_argument("--out", default="results", help="产出目录")
    args = ap.parse_args(argv)

    models = json.loads(pathlib.Path(args.models).read_text(encoding="utf-8"))["models"]
    scenarios = json.loads(
        pathlib.Path(args.scenarios).read_text(encoding="utf-8"))["scenarios"]

    results = [select_for_scenario(s, models) for s in scenarios]
    payload = {
        "criteria_order": CRITERIA_ORDER,
        "criteria_note": (
            "顺序不能换。商用授权必须是第一步且一票否决：它是这五步里唯一一个"
            "过不了就完全出局的维度，后四步都是程度问题。"),
        "vram_basis_note": (
            "可行性过滤用夹具原始显存值（估算值只含权重、不含 KV Cache）；"
            "实际配机值见 results/vram_budget.md，按 ≥20% 上浮。"),
        "source_note": (
            "许可证与规格来自 fixtures/models.json 快照，正式选型前必须回到"
            "各模型官方仓库的 LICENSE 与 config.json 重新核对并标注取数日期。"),
        "results": results,
    }

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "selection.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")

    for r in results:
        print(f"{r['scenario_id']}: selected={r['selected'] or 'null（可行集为空）'}"
              f"  feasible={r['feasible_set'] or '[]'}")
    print(f"written={dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
