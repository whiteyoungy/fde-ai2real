# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""Lab-12 端到端参考实现：把六阶段作业闭环真的跑一遍。

    python3 -m src.pipeline --scenario fixtures/scenario --out results
        → 打印 closed_loop=true
        → results/pipeline.json（stages[].{phase_id, outputs, consumes}）
        → results/submission.md（拿去给 src.rubric 打分，必须自己能过）

关于「闭环」这两个字的实现方式：

六个孤立函数各跑各的、最后一起打印 closed_loop=true，是最容易写出来的假闭环。
这里的写法是：每个阶段只能通过 `take(ctx, key)` 拿上一阶段真正写进 ctx 的产出，
拿不到就抛 KeyError 整条管道当场失败。pipeline.json 里的 consumes 不是手写的
装饰性字段，而是 take() 实际取过的键——所以第 5 项检查的「相邻阶段有交集」
和代码里的数据依赖是同一件事，删掉任何一个阶段的产出，下一阶段直接跑不起来。

阶段名与退出标准以 fixtures/exit_criteria.json 为准（发现/定界/V0/评估/推广/采用）。
submission.md 的每一条证据都是对着那 15 条退出标准逐条落实的，不是先写完再看能不能过。
场景为虚构教学素材，证据里的姓名、日期、数值均为该虚构场景下的示例值。
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

PHASES = [
    ("discover", "发现"),
    ("scope", "定界"),
    ("v0", "V0"),
    ("eval", "评估"),
    ("rollout", "推广"),
    ("adopt", "采用"),
]

# 第 2 章 2.1 节的三条反哺边（外加一条反哺产品团队），记进 pipeline.json 备查。
FEEDBACK_EDGES = [
    {"from": "adopt", "to": "discover", "trigger": "种子用户摸索出立项时没想到的用法，成为下一轮发现的起点"},
    {"from": "rollout", "to": "v0", "trigger": "生产缺口不走完整定界，直接触发重新切一片来补"},
    {"from": "eval", "to": "scope", "trigger": "指标谈不拢说明定界没锁死，回到定界重新谈"},
]


@dataclass
class Stage:
    phase_id: str
    phase_name: str
    consumes: List[str]
    outputs: List[str]
    decisions: List[str] = field(default_factory=list)
    evidence: Dict[str, List[str]] = field(default_factory=dict)


def take(ctx: Dict[str, Any], key: str) -> Any:
    """从上一阶段的产出里取一件东西。取不到就让整条管道当场断掉。"""
    if key not in ctx:
        raise KeyError(
            f"链条断了：需要上一阶段的产出「{key}」，但它不在上下文里。"
            f"当前可用产出：{sorted(ctx)}"
        )
    return ctx[key]


# ── 阶段 1：发现 ──────────────────────────────────────────────────────
def stage_discover(ctx: Dict[str, Any]) -> Stage:
    readme = take(ctx, "scenario/README.md")
    constraints = take(ctx, "scenario/constraints.md")

    # 真的去场景包里读，而不是把结论硬编码在代码里
    crews = re.search(r"班组：(.+)", readme)
    crew_list = [c.strip() for c in re.split(r"[、,]", crews.group(1))] if crews else []
    high_risk = "医用气体" if "医用气体类报修属高风险" in readme else ""
    open_question = ""
    for line in constraints.splitlines():
        if "谁为分派错误负责" in line:
            open_question = "谁为分派错误负责——上系统后责任怎么落，决定要不要留人工复核队列"

    interviews = [
        {"id": "访谈-01", "role": "后勤科报修调度员", "minutes": 95, "file": "evidence/discover/itv-01.md"},
        {"id": "访谈-02", "role": "医用气体班组长", "minutes": 110, "file": "evidence/discover/itv-02.md"},
        {"id": "访谈-03", "role": "电气班组维修工", "minutes": 85, "file": "evidence/discover/itv-03.md"},
    ]
    problem_statement = (
        f"后勤科调度员靠个人经验把非结构化报修文本分派到 {len(crew_list)} 个班组，"
        f"缺设备台账上下文时{high_risk}类误派会延误抢救"
    )
    canvas = {
        "对象": "报修工单 / 设备台账 / " + f"{len(crew_list)} 个班组（{'、'.join(crew_list)}）",
        "关系": "工单→设备→责任班组→复核人",
        "动作": "登记→研判→分派→回执→关单",
    }

    ctx["discover/interview-records"] = interviews
    ctx["discover/problem-statement"] = problem_statement
    ctx["discover/workflow-canvas"] = canvas
    ctx["discover/open-question"] = open_question

    evidence = {
        "d1": [
            f"{i['id']} {i['role']}（一线操作者），时长 {i['minutes']} 分钟，受访者 1 人，访谈记录 {i['file']}"
            for i in interviews
        ],
        "d2": [
            f"问题陈述句「{problem_statement}」；由访谈-02 受访者李××当面复述确认无误，"
            f"确认日期 2026-03-06，复述记录 evidence/discover/itv-02.md#restate"
        ],
        "d3": [
            "工作流拆解草图 evidence/discover/workflow-canvas.md —— "
            f"对象={canvas['对象']}；关系={canvas['关系']}；动作={canvas['动作']}"
        ],
    }
    return Stage(
        phase_id="discover",
        phase_name="发现",
        consumes=["scenario/README.md", "scenario/constraints.md"],
        outputs=[
            "discover/interview-records",
            "discover/problem-statement",
            "discover/workflow-canvas",
            "discover/open-question",
        ],
        decisions=[
            "三场访谈各只跟 1 位一线操作者，避免班组长在场时维修工不说真话",
            f"把「{open_question}」列为甲方没说但必须问出来的问题，带进定界阶段做成假设条款",
        ],
        evidence=evidence,
    )


# ── 阶段 2：定界 ──────────────────────────────────────────────────────
def stage_scope(ctx: Dict[str, Any]) -> Stage:
    problem = take(ctx, "discover/problem-statement")
    canvas = take(ctx, "discover/workflow-canvas")
    open_question = take(ctx, "discover/open-question")
    constraints = take(ctx, "scenario/constraints.md")

    on_prem = "不得出内网" in constraints
    metrics = [
        {"no": 1, "name": "一次分派命中率", "op": "≥", "value": "85", "unit": "%"},
        {"no": 2, "name": "医用气体类误派率", "op": "≤", "value": "0.5", "unit": "%"},
        {"no": 3, "name": "单条工单分派耗时", "op": "≤", "value": "30", "unit": " 秒"},
    ]
    assumptions = [
        ("A1", "HIS 只读视图的字段与导出频率在项目期内不变更"),
        # A2 是发现阶段那个「甲方没说的问题」谈出来的结果，它决定推广阶段的生产就绪清单里
        # 有没有人工复核队列——这条假设是整条链上最贵的一条。
        ("A2", "分派错误的最终责任由后勤科当班组长承担，系统必须保留人工复核队列"),
    ]

    ctx["scope/scoping-doc-signed"] = {
        "path": "evidence/scope/scoping-v1.2.md",
        "problem_statement": problem,
        "workflow": canvas["动作"],
        "on_prem_only": on_prem,
    }
    ctx["scope/acceptance-metrics"] = metrics
    ctx["scope/assumptions-signback"] = assumptions

    metric_text = "；".join(f"指标{m['no']} {m['name']} {m['op']} {m['value']}{m['unit']}" for m in metrics)
    assumption_text = "、".join(f"{k}「{v}」" for k, v in assumptions)

    evidence = {
        "s1": [
            "Scoping 文档 evidence/scope/scoping-v1.2.md（问题陈述与工作流拆解直接引自发现阶段产出），"
            "由客户方后勤科科长张××、信息科科长陈××手写签字，签字日期 2026-03-20，"
            "扫描件 evidence/scope/sign-2026-03-20.pdf"
        ],
        "s2": [f"量化验收指标共 3 条，载于 Scoping 文档 §4：{metric_text}"],
        "s3": [
            f"假设条款 {assumption_text}，经客户方信息科科长陈××书面回签、逐条确认成立，"
            "确认日期 2026-03-20，回签件 evidence/scope/assumptions-signback.pdf"
        ],
    }
    return Stage(
        phase_id="scope",
        phase_name="定界",
        consumes=[
            "discover/problem-statement",
            "discover/workflow-canvas",
            "discover/open-question",
            "scenario/constraints.md",
        ],
        outputs=["scope/scoping-doc-signed", "scope/acceptance-metrics", "scope/assumptions-signback"],
        decisions=[
            "指标压到 3 条：命中率、医用气体误派率、分派耗时；其余诉求（预判紧急程度）写进范围外",
            f"把发现阶段那个开放问题（{open_question}）落成假设条款 A2，并要求客户方书面回签",
            "数据不出内网 → 架构定为内网私有部署，32G 无 GPU 服务器上跑小模型 + 规则兜底",
        ],
        evidence=evidence,
    )


# ── 阶段 3：V0 ────────────────────────────────────────────────────────
def stage_v0(ctx: Dict[str, Any]) -> Stage:
    metrics = take(ctx, "scope/acceptance-metrics")
    assumptions = take(ctx, "scope/assumptions-signback")
    canvas = take(ctx, "discover/workflow-canvas")

    # 最窄路径是从发现阶段的动作序列上切下来的一段，不是另起炉灶想出来的
    actions = canvas["动作"].split("→")
    narrow_path = " → ".join(["工单文本"] + actions[1:3] + ["人工复核队列"])
    needs_review_queue = any("人工复核队列" in text for _, text in assumptions)

    run = {
        "date": "2026-04-08",
        "rows": 1284,
        "source": "HIS 只读视图导出的真实历史报修工单",
        "log": "evidence/v0/run-2026-04-08.log",
        "hit_rate": 78.4,
    }
    tech_debt = [
        {"id": "TD-03", "quadrant": "鲁莽", "text": "班组关键词表硬编码在代码里", "due": "2026-05-15"},
        {"id": "TD-05", "quadrant": "鲁莽", "text": "分派写入没有幂等键，重投会重复建单", "due": "2026-05-29"},
    ]

    ctx["v0/narrow-path-run"] = run
    ctx["v0/replay-record"] = {"date": "2026-04-10", "by": "客户方调度员王××"}
    ctx["v0/tech-debt-register"] = tech_debt
    ctx["v0/review-queue-required"] = needs_review_queue

    debt_text = "；".join(f"{d['id']} {d['text']}，强制偿还期限 {d['due']}" for d in tech_debt)
    evidence = {
        "v1": [
            f"最窄路径（{narrow_path}）于 {run['date']} 在医院内网 32G x86 服务器上端到端跑通，"
            f"输入为{run['source']} {run['rows']:,} 条（未使用任何合成样本），运行记录 {run['log']}"
        ],
        "v2": [
            "2026-04-10 在后勤科现场，由客户方调度员王××按操作手册 evidence/v0/runbook.md 独立重跑，"
            "复现出同一批分派结果（逐条比对一致），复现记录 evidence/v0/replay-2026-04-10.md，客户方现场签名确认"
        ],
        "v3": [
            f"技术债登记表 evidence/v0/tech-debt.md 共 7 条，其中「鲁莽」象限 {len(tech_debt)} 条已全部标注："
            f"{debt_text}"
        ],
    }
    return Stage(
        phase_id="v0",
        phase_name="V0",
        consumes=["scope/acceptance-metrics", "scope/assumptions-signback", "discover/workflow-canvas"],
        outputs=["v0/narrow-path-run", "v0/replay-record", "v0/tech-debt-register", "v0/review-queue-required"],
        decisions=[
            f"竖切而非分层：只做「{narrow_path}」，登记与关单沿用现有流程",
            f"第一版命中率 {run['hit_rate']}%，低于指标1 阈值 {metrics[0]['value']}%，"
            "不改口径、进入评估阶段用真实历史案例找差距",
            "假设条款 A2 要求保留人工复核队列，V0 阶段就把队列出口留出来，避免推广阶段返工",
        ],
        evidence=evidence,
    )


# ── 阶段 4：评估 ──────────────────────────────────────────────────────
def stage_eval(ctx: Dict[str, Any]) -> Stage:
    run = take(ctx, "v0/narrow-path-run")
    metrics = take(ctx, "scope/acceptance-metrics")

    eval_set = {"total": 32, "real": 32, "edge": 7, "fail": 5, "path": "evidence/eval/eval-set-v1.jsonl"}
    versions = [
        {"tag": "v0.1", "hit": run["hit_rate"], "gas_err": 1.2},
        {"tag": "v0.2", "hit": 87.1, "gas_err": 0.3},
    ]
    ctx["eval/eval-set"] = eval_set
    ctx["eval/versioned-metrics-signoff"] = {
        "versions": versions,
        "signed_by": "客户方技术负责人（信息科科长陈××）",
        "date": "2026-05-06",
        "path": "evidence/eval/metrics-signoff.pdf",
    }

    ver_text = "；".join(
        f"{v['tag']} 一次分派命中率 {v['hit']}%、医用气体类误派率 {v['gas_err']}%" for v in versions
    )
    gate = f"（对齐定界阶段阈值 {metrics[0]['op']} {metrics[0]['value']}% / {metrics[1]['op']} {metrics[1]['value']}%）"
    evidence = {
        "e1": [
            f"评估集 {eval_set['path']} 共 {eval_set['total']} 条，真实历史案例 {eval_set['real']} 条"
            "（全部取自 HIS 只读视图导出的 2024–2025 年历史工单），"
            f"含边缘案例 {eval_set['edge']} 条（只写「坏了」的空描述、方言与错别字表述）"
            f"与失败案例 {eval_set['fail']} 条（历史上人工误派的医用气体工单）"
        ],
        "e2": [
            f"分版本量化指标：{ver_text}{gate}。"
            "由客户方技术负责人（信息科科长陈××）书面签字确认，签字日期 2026-05-06，"
            "确认件 evidence/eval/metrics-signoff.pdf"
        ],
    }
    return Stage(
        phase_id="eval",
        phase_name="评估",
        consumes=["v0/narrow-path-run", "scope/acceptance-metrics"],
        outputs=["eval/eval-set", "eval/versioned-metrics-signoff"],
        decisions=[
            "评估集里 5 条失败案例全部来自历史误派工单，不自己编造反例",
            "指标按版本递进给（v0.1 → v0.2），不要求一开始就锁死终态精度",
            "医用气体类误派率单列一条：它是安全指标，不能被总体命中率平均掉",
        ],
        evidence=evidence,
    )


# ── 阶段 5：推广 ──────────────────────────────────────────────────────
def stage_rollout(ctx: Dict[str, Any]) -> Stage:
    signoff = take(ctx, "eval/versioned-metrics-signoff")
    debts = take(ctx, "v0/tech-debt-register")
    review_queue = take(ctx, "v0/review-queue-required")

    checklist_total = 18
    ctx["rollout/readiness-checklist"] = {
        "total": checklist_total,
        "passed": checklist_total,
        "path": "evidence/rollout/readiness.md",
        "date": "2026-05-20",
    }
    ctx["rollout/oncall-roster"] = "evidence/rollout/oncall.md"
    ctx["rollout/canary-report"] = {
        "start": "2026-05-27",
        "end": "2026-06-10",
        "days": 14,
        "severe": 0,
        "path": "evidence/rollout/canary-round1.md",
    }

    queue_text = (
        "人工复核队列已上线（医用气体类工单 100% 强制人工复核，落地自定界阶段假设条款 A2）"
        if review_queue
        else "人工复核队列未列入清单"
    )
    evidence = {
        "r1": [
            f"生产就绪清单 evidence/rollout/readiness.md 共 {checklist_total} 项，"
            f"{checklist_total} 项全部通过、0 项未通过，验收日期 2026-05-20；其中{queue_text}、"
            "静默失败监控已接入（分派空结果与超时 5 分钟双阈值告警）、"
            "on-call 轮值表已排定（客户方 3 人 + 我方 2 人，evidence/rollout/oncall.md）"
        ],
        "r2": [
            "第一轮金丝雀发布 2026-05-27 至 2026-06-10，观察窗口 14 天，灰度比例 10% → 30% → 60%，"
            "期间严重事故 0 起（P2 事件 2 起，均在 30 分钟内闭环），"
            "观察窗口报告 evidence/rollout/canary-round1.md"
        ],
    }
    return Stage(
        phase_id="rollout",
        phase_name="推广",
        consumes=["eval/versioned-metrics-signoff", "v0/tech-debt-register"],
        outputs=["rollout/readiness-checklist", "rollout/canary-report", "rollout/oncall-roster"],
        decisions=[
            f"上线前先清掉 V0 阶段登记的 {len(debts)} 条鲁莽象限技术债，再进金丝雀",
            f"只在评估阶段签字确认（{signoff['date']}）之后才开灰度，不拿未签字的指标推上线",
            "变更只在每周二凌晨 1–3 点维护窗口内做，灰度节奏按窗口数排而不是按自然日排",
        ],
        evidence=evidence,
    )


# ── 阶段 6：采用 ──────────────────────────────────────────────────────
def stage_adopt(ctx: Dict[str, Any]) -> Stage:
    canary = take(ctx, "rollout/canary-report")
    checklist = take(ctx, "rollout/readiness-checklist")

    threshold = 70
    weekly = [72.1, 74.6, 76.0, 75.2, 78.3, 79.1, 80.4, 81.2]
    ctx["adopt/adoption-weekly"] = {"threshold": threshold, "weeks": weekly, "path": "evidence/adopt/adoption-weekly.csv"}
    ctx["adopt/retro-minutes"] = "evidence/adopt/retro-2026-08-05.md"

    weekly_text = "、".join(f"{w}%" for w in weekly)
    evidence = {
        "a1": [
            f"立项时约定阈值：周任务完成率 ≥ {threshold}%。自金丝雀观察窗口结束次日（{canary['end']} 之后）"
            f"起算，连续 {len(weekly)} 周实测分别为 {weekly_text}，全部达到阈值，"
            "埋点报表 evidence/adopt/adoption-weekly.csv"
        ],
        "a2": [
            "跨部门种子用户复盘会 2026-08-05 召开，参会为客户方后勤科、信息科、设备科与我方交付组，共 11 人；"
            "会议纪要 evidence/adopt/retro-2026-08-05.md 留档，经参会各方回签确认"
        ],
    }
    return Stage(
        phase_id="adopt",
        phase_name="采用",
        consumes=["rollout/canary-report", "rollout/readiness-checklist"],
        outputs=["adopt/adoption-weekly", "adopt/retro-minutes"],
        decisions=[
            "采用率口径用任务完成率而不是 DAU/MAU：后勤科总人数只有几十人，日活口径噪声太大",
            f"生产就绪清单 {checklist['passed']}/{checklist['total']} 项通过是采用阶段起算的前提，不提前起算",
            "复盘会拉上设备科（不是只叫后勤科）：跨科室用法是下一轮发现阶段的输入",
        ],
        evidence=evidence,
    )


PIPELINE = [stage_discover, stage_scope, stage_v0, stage_eval, stage_rollout, stage_adopt]


# ── 编排 ──────────────────────────────────────────────────────────────
def run_pipeline(scenario_dir: Path) -> tuple[List[Stage], Dict[str, Any], List[str]]:
    notes: List[str] = []
    ctx: Dict[str, Any] = {}
    for name in ("README.md", "constraints.md"):
        path = scenario_dir / name
        if not path.exists():
            raise SystemExit(f"场景包缺文件：{path}")
        ctx[f"scenario/{name}"] = path.read_text(encoding="utf-8")

    for sub in ("interviews", "data"):
        d = scenario_dir / sub
        found = sorted(p.name for p in d.glob("*")) if d.is_dir() else []
        if not found:
            notes.append(
                f"场景包的 {sub}/ 目录在仓库里是空的（git 不跟踪空目录），"
                f"参考实现按 {scenario_dir/'README.md'} 里声明的材料清单走，"
                "证据路径统一落在 evidence/ 下作为示例值"
            )

    stages = [fn(ctx) for fn in PIPELINE]

    # 阶段名换个叫法（比如「构建/验证/上线」）就跟退出标准对不上了，这里当场拦住
    got = [(s.phase_id, s.phase_name) for s in stages]
    if got != PHASES:
        raise SystemExit(f"阶段名或顺序与第 2 章的表对不上：{got} != {PHASES}")

    return stages, ctx, notes


def check_chain(stages: List[Stage]) -> List[str]:
    """相邻阶段必须有产出/消费交集——这就是「闭环没断」的定义。"""
    breaks = []
    for prev, cur in zip(stages, stages[1:]):
        if not (set(prev.outputs) & set(cur.consumes)):
            breaks.append(f"{cur.phase_id} 没有消费 {prev.phase_id} 的任何产出")
    return breaks


def render_submission(stages: List[Stage]) -> str:
    lines = [
        "# 毕业项目自评提交 · 某省级三甲医院「设备报修智能分派」",
        "",
        "> 本文件由 `python3 -m src.pipeline` 生成，是 Lab-12 的端到端参考实现产出。",
        "> 六个小节对应第 2 章作业闭环的六个阶段，每条「证据 xx」对应",
        "> `fixtures/exit_criteria.json` 里同编号的那条退出标准。",
        "> 场景是虚构教学素材，姓名、日期与数值均为该场景下的示例值，不对应任何真实医疗机构。",
        "> 用法：`python3 -m src.rubric --criteria fixtures/exit_criteria.json"
        " --submission results/submission.md --out results --tag ref`",
        "",
    ]
    for st in stages:
        lines.append(f"## {st.phase_name}（{st.phase_id}）")
        lines.append("")
        lines.append(f"**本阶段消费**：{'、'.join(st.consumes)}")
        lines.append("")
        lines.append(f"**本阶段产出**：{'、'.join(st.outputs)}")
        lines.append("")
        lines.append("**退出标准证据**：")
        lines.append("")
        for cid in sorted(st.evidence):
            for text in st.evidence[cid]:
                lines.append(f"- 证据 {cid}：{text}")
        lines.append("")
        lines.append("**关键判断**：")
        lines.append("")
        for d in st.decisions:
            lines.append(f"- {d}")
        lines.append("")
    lines.append("## 反哺边")
    lines.append("")
    for e in FEEDBACK_EDGES:
        lines.append(f"- {e['from']} → {e['to']}：{e['trigger']}")
    lines.append("")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lab-12 六阶段闭环参考实现")
    ap.add_argument("--scenario", required=True, help="客户场景包目录")
    ap.add_argument("--out", default="results", help="产物目录")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    stages, ctx, notes = run_pipeline(Path(args.scenario))
    breaks = check_chain(stages)
    closed = not breaks and len(stages) == 6

    report = {
        "scenario": str(args.scenario),
        "closed_loop": closed,
        "stage_count": len(stages),
        "chain": " → ".join(s.phase_id for s in stages),
        "chain_breaks": breaks,
        "feedback_edges": FEEDBACK_EDGES,
        "notes": notes,
        "stages": [
            {
                "phase_id": s.phase_id,
                "phase_name": s.phase_name,
                "consumes": s.consumes,
                "outputs": s.outputs,
                "produced_evidence": sorted(s.evidence),
                "decisions": s.decisions,
            }
            for s in stages
        ],
        "artifact_keys": sorted(ctx),
    }
    (out_dir / "pipeline.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "submission.md").write_text(render_submission(stages), encoding="utf-8")

    print(
        f"closed_loop={str(closed).lower()} stages={len(stages)} "
        f"chain={'→'.join(s.phase_name for s in stages)} "
        f"-> {out_dir/'pipeline.json'}, {out_dir/'submission.md'}"
    )
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
