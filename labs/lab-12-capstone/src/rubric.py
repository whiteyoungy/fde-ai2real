# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""Lab-12 自评量表：既生成量表，也拿量表给一份提交打分。

两个模式（探针 CLI 契约见 README）：

    python3 -m src.rubric --criteria fixtures/exit_criteria.json --out results
        → results/rubric.json，含 items[].{criterion_id, phase_id, question, evidence_required}

    python3 -m src.rubric --criteria ... --submission <文件> --out results --tag <ref|bad>
        → results/score_<tag>.json，含 passed 与 items[].{criterion_id, met, reason}

设计上的两条硬约束：

1. **判分必须确定性**。全部判据是纯字符串/正则规则，不调模型、不看时间、不读环境变量。
   verify.sh 会反复跑，同一份提交每次必须得到同一个结论；否则「量表」就只是一次随机抽签。
   模型可以用来润色说明文字，但绝不参与「达标 / 不达标」的裁决。

2. **判事实，不判措辞**。第 26 章自检题第 3 问的负例（fixtures/bad_submission/）每个阶段的
   小节标题都在，问题在内容里——所以量表不能只查「有没有对应小节」。每条退出标准都被拆成
   若干条可核验的断言：条数、时长、日期、签字人、文件路径、以及「不许出现 mock / 口头 /
   还没登记」这类反向信号。README 延伸练习 3 问「改几个字能不能过」，答案应当是不能：
   改措辞过不了条数与日期的断言。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

# 第 2 章原则：退出标准必须能用是/否回答。下面这些表述回答不了，
# 出现在提交的某个阶段小节里，等于这个阶段没有检验过。
VAGUE_WORDS = [
    "应该没问题",
    "基本完成",
    "大致",
    "差不多",
    "心里有数",
    "客户满意了",
    "需求明确了",
    "问题不大",
    "回头再补",
]

# 实际扫描用正则而不是字面量：负例夹具写的是「范围大家心里都有数」，
# 只匹配字面的「心里有数」会漏掉——量表判的是这种说法本身，不是某个特定写法。
VAGUE_PATTERNS: List[Tuple[str, str]] = [
    (r"应该没(什么)?问题", "应该没问题"),
    (r"基本(完成|做完|齐了)", "基本完成"),
    (r"大致(上)?", "大致"),
    (r"差不多", "差不多"),
    (r"心里(都|也)?有数", "心里有数"),
    (r"客户(应该)?满意了", "客户满意了"),
    (r"需求(已经)?明确了", "需求明确了"),
    (r"问题不大", "问题不大"),
    (r"回头再补", "回头再补"),
]

DATE_RE = r"\d{4}-\d{2}-\d{2}"
Check = Tuple[str, Callable[[str], bool]]


# ── 判据小工具 ────────────────────────────────────────────────────────
def _uniq(pattern: str, text: str) -> int:
    return len(set(re.findall(pattern, text)))


def _ints(pattern: str, text: str) -> List[int]:
    return [int(x.replace(",", "")) for x in re.findall(pattern, text)]


def _first_int(pattern: str, text: str) -> int | None:
    got = _ints(pattern, text)
    return got[0] if got else None


def _all_in(text: str, *subs: str) -> bool:
    return all(s in text for s in subs)


def _dates(text: str) -> List[str]:
    return re.findall(DATE_RE, text)


def _paths(text: str) -> List[str]:
    return re.findall(r"evidence/[\w\-./#]+", text)


# ── 15 条退出标准的判据定义 ──────────────────────────────────────────
# 每条 = 一个是/否问法 + 要拿什么证据来判 + 若干条可核验断言 + 反向信号。
# 断言全部为真才算 met；任意一条不成立，reason 里逐条列出不成立的是哪些。
SPEC: Dict[str, dict] = {
    # ── 发现 ──
    "d1": {
        "question": "是否已完成至少 3 场情境访谈，且每场时长不超过 120 分钟、每场只有 1 位一线操作者受访？",
        "evidence": "三条以上访谈记录条目，每条写明访谈编号、受访岗位、时长（分钟）、受访者人数与访谈记录文件路径",
        "checks": [
            ("访谈记录条目少于 3 场（按访谈编号计）", lambda t: _uniq(r"访谈-\d+", t) >= 3),
            (
                "没有逐场写明时长，或存在超过 120 分钟的场次",
                lambda t: len(_ints(r"时长\s*(\d+)\s*分钟", t)) >= 3
                and max(_ints(r"时长\s*(\d+)\s*分钟", t)) <= 120,
            ),
            ("没有逐场写明「受访者 1 人」，无法确认每场只跟 1 位一线操作者", lambda t: len(re.findall(r"受访者\s*1\s*人", t)) >= 3),
            ("没有给出访谈记录的文件路径", lambda t: len(_paths(t)) >= 3),
        ],
        "forbid": ["座谈会", "一起聊"],
    },
    "d2": {
        "question": "是否产出了一份问题陈述句，并由受访者当面复述确认无误、留下确认日期？",
        "evidence": "问题陈述句原文（「」引出）、当面复述确认的记录、确认人与确认日期、记录文件路径",
        "checks": [
            ("没有给出问题陈述句原文", lambda t: bool(re.search(r"问题陈述句\s*「[^」]{10,}」", t))),
            ("没有证据表明由受访者当面复述并确认无误", lambda t: _all_in(t, "当面复述", "确认无误")),
            ("没有写明确认日期", lambda t: len(_dates(t)) >= 1),
            ("没有给出记录文件路径", lambda t: len(_paths(t)) >= 1),
        ],
        "forbid": ["口头认可", "我理解的是"],
    },
    "d3": {
        "question": "是否产出了一版工作流拆解草图，且明确覆盖对象、关系、动作三要素？",
        "evidence": "工作流拆解草图文件路径，以及草图中对象 / 关系 / 动作三要素各自的具体内容",
        "checks": [
            ("没有给出工作流拆解草图的文件路径", lambda t: "工作流拆解草图" in t and len(_paths(t)) >= 1),
            ("三要素没有写全（需同时写明对象= / 关系= / 动作=）", lambda t: _all_in(t, "对象=", "关系=", "动作=")),
            ("动作要素没有拆到可核验的步骤序列", lambda t: t.count("→") >= 2),
        ],
        "forbid": [],
    },
    # ── 定界 ──
    "s1": {
        "question": "是否拿到了客户签字的 Scoping 文档，且能查到签字人与签字日期？",
        "evidence": "Scoping 文档文件路径、客户方签字人姓名与岗位、签字日期、签字扫描件路径",
        "checks": [
            ("没有给出 Scoping 文档的文件路径", lambda t: "Scoping 文档" in t and len(_paths(t)) >= 1),
            ("没有写明客户方签字人", lambda t: "签字" in t and bool(re.search(r"(科长|主任|负责人|经理)", t))),
            ("没有写明签字日期", lambda t: bool(re.search(r"签字日期\s*" + DATE_RE, t))),
            ("没有留存签字件（扫描件 / 回签件）路径", lambda t: bool(re.search(r"(扫描件|回签件|签字件)\s*evidence/", t))),
        ],
        # 第 2 章：口头共识在争议时一文不值，这里是硬反向信号。
        "forbid": ["未签字", "没签字", "口头确认", "口头同意", "待签字"],
    },
    "s2": {
        "question": "量化验收指标是否为 1–3 条，且每一条都写了可核验的数值阈值？",
        "evidence": "验收指标条数声明、逐条指标名与数值阈值（含 ≥ 或 ≤ 与单位）、指标所在文档章节",
        "checks": [
            (
                "没有声明验收指标条数，或条数超过 3 条",
                lambda t: (_first_int(r"量化验收指标共\s*(\d+)\s*条", t) or 0) in (1, 2, 3),
            ),
            (
                "逐条列出的指标数与声明的条数对不上",
                lambda t: _uniq(r"指标(\d)\s", t) == (_first_int(r"量化验收指标共\s*(\d+)\s*条", t) or -1),
            ),
            (
                "存在没有数值阈值的指标（每条都要有 ≥ 或 ≤ 加数值）",
                lambda t: len(re.findall(r"[≥≤]\s*[\d.]+", t)) >= (_first_int(r"量化验收指标共\s*(\d+)\s*条", t) or 99),
            ),
            ("没有写明指标载于哪份文档的哪一节", lambda t: bool(re.search(r"(Scoping 文档|SOW)\s*§", t))),
        ],
        "forbid": ["尽量", "越高越好"],
    },
    "s3": {
        "question": "假设条款是否已由客户方书面确认成立，并留有确认人、确认日期与回签件？",
        "evidence": "逐条假设条款原文、客户方书面回签的确认人与岗位、确认日期、回签件文件路径",
        "checks": [
            ("没有逐条列出假设条款", lambda t: "假设条款" in t and _uniq(r"A\d", t) >= 2),
            ("没有证据表明客户方是书面确认（不是甲方单方面写完就算数）", lambda t: _all_in(t, "书面") and ("回签" in t or "确认成立" in t)),
            ("没有写明书面确认的日期", lambda t: bool(re.search(r"确认日期\s*" + DATE_RE, t))),
            ("没有留存回签件路径", lambda t: len(_paths(t)) >= 1),
        ],
        "forbid": ["口头", "未确认", "默认成立"],
    },
    # ── V0 ──
    "v1": {
        "question": "最窄路径是否用真实数据（非 mock）在客户环境端到端跑通过至少一次，并留有运行记录？",
        "evidence": "最窄路径的起止环节、跑通日期与运行环境、真实数据来源与条数、运行记录文件路径",
        "checks": [
            ("没有写明跑的是哪条最窄路径、是否端到端", lambda t: _all_in(t, "最窄路径", "端到端", "跑通")),
            (
                "没有写明真实数据来源与条数（真实数据是硬要求，mock 只验证了界面能不能画出来）",
                lambda t: "真实" in t and bool(re.search(r"[\d,]+\s*条", t)),
            ),
            ("没有写明跑通日期", lambda t: len(_dates(t)) >= 1),
            ("没有留存运行记录路径", lambda t: len(_paths(t)) >= 1),
        ],
        "forbid": ["mock", "Mock", "MOCK", "模拟数据", "自己造", "照着编", "编的", "假数据"],
    },
    "v2": {
        "question": "客户方是否在现场独立复现过一次，并留有复现记录与客户方确认？",
        "evidence": "复现日期与地点、客户方操作人姓名与岗位、复现结论、复现记录文件路径与客户方签名",
        "checks": [
            ("没有证据表明是客户方自己现场复现（我方演示不算）", lambda t: _all_in(t, "客户方", "现场", "复现")),
            ("没有写明客户方操作人的岗位", lambda t: bool(re.search(r"(调度员|班组长|工程师|科长|操作员)", t))),
            ("没有写明复现日期", lambda t: len(_dates(t)) >= 1),
            ("没有留存复现记录路径或客户方确认", lambda t: len(_paths(t)) >= 1 and ("签名" in t or "确认" in t)),
        ],
        "forbid": ["我方演示", "远程截图", "录屏代替"],
    },
    "v3": {
        "question": "技术债登记表中「鲁莽」象限条目是否已全部标注，并逐条设定了强制偿还期限？",
        "evidence": "技术债登记表文件路径、条目总数、鲁莽象限条目编号与内容、每条的强制偿还期限日期",
        "checks": [
            ("没有给出技术债登记表路径", lambda t: "技术债登记表" in t and len(_paths(t)) >= 1),
            ("没有标出「鲁莽」象限条目并说明是否已全部标注", lambda t: "鲁莽" in t and "全部标注" in t),
            (
                "鲁莽象限条目没有逐条设定强制偿还期限（日期）",
                lambda t: len(re.findall(r"强制偿还期限\s*" + DATE_RE, t)) >= 1,
            ),
            ("没有给出条目编号，无法逐条追溯", lambda t: _uniq(r"TD-\d+", t) >= 1),
        ],
        "forbid": ["还没登记", "未登记", "来不及", "后面再补"],
    },
    # ── 评估 ──
    "e1": {
        "question": "评估集是否包含至少 20 条来自真实历史案例的测试用例，并覆盖边缘案例与失败案例？",
        "evidence": "评估集文件路径、真实历史案例条数与数据来源、边缘案例条数、失败案例条数",
        "checks": [
            (
                "来自真实历史案例的用例不足 20 条（自己编的用例不计入）",
                lambda t: (_first_int(r"真实历史案例\s*(\d+)\s*条", t) or 0) >= 20,
            ),
            ("没有写明真实历史案例的数据来源", lambda t: bool(re.search(r"(历史工单|历史案例|台账|只读视图)", t))),
            (
                "没有写明边缘案例与失败案例各多少条",
                lambda t: bool(re.search(r"边缘案例\s*\d+\s*条", t)) and bool(re.search(r"失败案例\s*\d+\s*条", t)),
            ),
            ("没有给出评估集文件路径", lambda t: len(_paths(t)) >= 1),
        ],
        "forbid": ["mock", "照着编", "编的", "自己造", "虚构用例"],
    },
    "e2": {
        "question": "分版本量化指标是否已由客户方技术负责人书面签字确认，并留有签字日期与确认件？",
        "evidence": "至少两个版本的指标数值、客户方技术负责人姓名与岗位、书面签字日期、确认件文件路径",
        "checks": [
            ("指标没有分版本给出（至少两个版本号）", lambda t: _uniq(r"v\d+\.\d+", t) >= 2),
            ("指标没有量化数值", lambda t: len(re.findall(r"[\d.]+\s*%", t)) >= 2),
            (
                "没有客户方技术负责人的书面签字",
                lambda t: _all_in(t, "技术负责人") and ("书面签字" in t or "签字确认" in t),
            ),
            ("没有写明签字日期或留存确认件路径", lambda t: bool(re.search(r"签字日期\s*" + DATE_RE, t)) and len(_paths(t)) >= 1),
        ],
        "forbid": ["还没找", "未签字", "待签字", "口头认可"],
    },
    # ── 推广 ──
    "r1": {
        "question": "生产就绪清单是否全部条目通过，且人工复核队列、静默失败监控、on-call 轮值表三项均已就位？",
        "evidence": "生产就绪清单文件路径、条目总数与通过数、人工复核队列 / 静默失败监控 / on-call 轮值表三项各自的落地说明与验收日期",
        "checks": [
            ("没有给出生产就绪清单路径与条目总数", lambda t: "生产就绪清单" in t and len(_paths(t)) >= 1),
            (
                "没有写明全部条目通过（需给出通过数与未通过数）",
                lambda t: bool(re.search(r"\d+\s*项全部通过", t)) and bool(re.search(r"0\s*项未通过", t)),
            ),
            (
                "三项必备条目没有写全：人工复核队列 / 静默失败监控 / on-call 轮值表",
                lambda t: _all_in(t, "人工复核队列", "静默失败监控", "on-call 轮值表"),
            ),
            ("没有写明清单验收日期", lambda t: len(_dates(t)) >= 1),
        ],
        "forbid": ["还在整理", "待整理", "清单未完成", "计划下周"],
    },
    "r2": {
        "question": "是否已完成至少一轮金丝雀发布观察窗口，且窗口内严重事故为 0 起？",
        "evidence": "金丝雀发布的起止日期与灰度比例、观察窗口天数、严重事故起数、观察窗口报告文件路径",
        "checks": [
            ("没有写明金丝雀发布的起止日期", lambda t: "金丝雀" in t and len(_dates(t)) >= 2),
            ("没有写明观察窗口天数与灰度比例", lambda t: bool(re.search(r"观察窗口\s*\d+\s*天", t)) and "%" in t),
            ("没有给出严重事故起数，或严重事故不为 0 起", lambda t: bool(re.search(r"严重事故\s*0\s*起", t))),
            ("没有留存观察窗口报告路径", lambda t: len(_paths(t)) >= 1),
        ],
        "forbid": ["计划下周", "尚未开始", "还没灰度", "准备灰度"],
    },
    # ── 采用 ──
    "a1": {
        "question": "采用率指标是否连续至少 4 周达到立项时约定的阈值，并有逐周实测值可查？",
        "evidence": "立项时约定的采用率阈值、连续达标周数、逐周实测数值、埋点报表文件路径",
        "checks": [
            ("没有写明连续达标周数，或不足 4 周", lambda t: (_first_int(r"连续\s*(\d+)\s*周", t) or 0) >= 4),
            ("没有写明立项时约定的阈值（需含数值）", lambda t: "阈值" in t and bool(re.search(r"[≥≤]\s*[\d.]+\s*%", t))),
            (
                "没有逐周实测值可查（需给出至少 4 个周实测数值）",
                lambda t: len(re.findall(r"[\d.]+\s*%", t)) >= 5,
            ),
            ("没有给出埋点报表路径", lambda t: len(_paths(t)) >= 1),
        ],
        "forbid": ["上线之后再看", "以后再看", "还没埋点", "看感觉"],
    },
    "a2": {
        "question": "是否召开了一次跨部门种子用户复盘会，并把会议纪要留档？",
        "evidence": "复盘会日期、参会的跨部门名单与人数、会议纪要文件路径、纪要的回签或确认方式",
        "checks": [
            ("没有证据表明是跨部门复盘会", lambda t: _all_in(t, "跨部门", "复盘会")),
            ("没有写明会议日期", lambda t: len(_dates(t)) >= 1),
            ("没有写明参会部门与人数（跨部门需至少两个客户方部门）", lambda t: bool(re.search(r"共\s*\d+\s*人", t)) and t.count("科") >= 2),
            ("会议纪要没有留档路径", lambda t: "会议纪要" in t and len(_paths(t)) >= 1),
        ],
        "forbid": ["没开成", "改到下次", "口头同步"],
    },
}


# ── 量表生成 ──────────────────────────────────────────────────────────
def load_criteria(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_rubric(criteria: dict) -> dict:
    items = []
    for phase in criteria["phases"]:
        for crit in phase["criteria"]:
            cid = crit["id"]
            spec = SPEC.get(cid)
            if spec is None:
                raise SystemExit(
                    f"量表没有覆盖退出标准 {cid}（{crit['text']}）——"
                    "exit_criteria.json 增加了条目，SPEC 必须同步补齐"
                )
            items.append(
                {
                    "criterion_id": cid,
                    "phase_id": phase["id"],
                    "phase_name": phase["name"],
                    "criterion_text": crit["text"],
                    "question": spec["question"],
                    "evidence_required": spec["evidence"],
                    "checks": [desc for desc, _ in spec["checks"]],
                    "disqualifiers": list(spec["forbid"]),
                }
            )
    return {
        "source": criteria.get("_source", ""),
        "principle": "每一条都能用是/否回答，且写明要拿什么证据来判；判据检的是事实（条数、日期、签字人、文件路径），不是措辞。",
        "phases": [{"id": p["id"], "name": p["name"]} for p in criteria["phases"]],
        "vague_words_rejected": list(VAGUE_WORDS),
        "items": items,
    }


# ── 提交解析与打分 ────────────────────────────────────────────────────
def split_sections(text: str, phases: List[dict]) -> Dict[str, str]:
    """按 markdown 标题把提交切成各阶段小节。

    标题里出现阶段名（发现 / 定界 / V0 / 评估 / 推广 / 采用）就归到该阶段。
    负例夹具用的是 `## 发现` 这种裸标题，参考实现用 `## 发现（discover）`，两种都能切。
    """
    names = {p["id"]: p["name"] for p in phases}
    sections: Dict[str, List[str]] = {pid: [] for pid in names}
    current = None
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            head = m.group(1)
            current = None
            for pid, name in names.items():
                if name.lower() in head.lower():
                    current = pid
                    break
            continue
        if current:
            sections[current].append(line)
    return {pid: "\n".join(lines) for pid, lines in sections.items()}


def extract_evidence(section: str, cid: str) -> str:
    """取出该阶段小节里标了「证据 <cid>」的条目，允许一条标准有多条证据。"""
    hits = []
    pat = re.compile(r"^\s*[-*]\s*证据\s*" + re.escape(cid) + r"\s*[:：]\s*(.+)$")
    for line in section.splitlines():
        m = pat.match(line)
        if m:
            hits.append(m.group(1).strip())
    return "\n".join(hits)


def judge(cid: str, spec: dict, section: str, phase_name: str) -> Tuple[bool, str]:
    reasons: List[str] = []

    if not section.strip():
        return False, f"提交里找不到「{phase_name}」阶段的小节，这条退出标准没有任何可核验的内容"

    evidence = extract_evidence(section, cid)
    if evidence:
        scan = evidence
    else:
        # 没有打标记的证据条目就退回整段小节来判——不让「漏写标记」变成免检，
        # 也不让「只写了小节标题」蒙混过关。
        scan = section
        reasons.append(f"没有提供带「证据 {cid}」标记的证据条目，只能按整段正文判")

    for desc, fn in spec["checks"]:
        try:
            passed = bool(fn(scan))
        except Exception:  # 判据自身异常一律按不达标处理，不静默放过
            passed = False
        if not passed:
            reasons.append(desc)

    for word in spec["forbid"]:
        if word in scan:
            reasons.append(f"证据里出现了「{word}」，与这条退出标准直接冲突")

    for pattern, label in VAGUE_PATTERNS:
        if re.search(pattern, section):
            reasons.append(f"该阶段用「{label}」这类模糊措辞代替证据——它回答不了是/否，不是退出标准")

    if reasons:
        # 去重但保持顺序，便于逐条对照改进
        seen, ordered = set(), []
        for r in reasons:
            if r not in seen:
                seen.add(r)
                ordered.append(r)
        return False, f"{phase_name}阶段：" + "；".join(ordered)
    return True, ""


def score(criteria: dict, submission_path: Path) -> dict:
    text = submission_path.read_text(encoding="utf-8")
    sections = split_sections(text, criteria["phases"])

    items = []
    for phase in criteria["phases"]:
        for crit in phase["criteria"]:
            cid = crit["id"]
            spec = SPEC[cid]
            met, reason = judge(cid, spec, sections.get(phase["id"], ""), phase["name"])
            items.append(
                {
                    "criterion_id": cid,
                    "phase_id": phase["id"],
                    "phase_name": phase["name"],
                    "criterion_text": crit["text"],
                    "question": spec["question"],
                    "evidence_required": spec["evidence"],
                    "met": met,
                    "reason": reason,
                }
            )

    unmet = [i for i in items if not i["met"]]
    by_phase = {}
    for phase in criteria["phases"]:
        pid = phase["id"]
        phase_items = [i for i in items if i["phase_id"] == pid]
        by_phase[pid] = {
            "name": phase["name"],
            "met": sum(1 for i in phase_items if i["met"]),
            "total": len(phase_items),
        }

    return {
        "submission": str(submission_path),
        "passed": len(unmet) == 0,
        "met_count": len(items) - len(unmet),
        "total_count": len(items),
        "unmet_count": len(unmet),
        "by_phase": by_phase,
        "items": items,
    }


# ── CLI ───────────────────────────────────────────────────────────────
def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lab-12 自评量表：生成量表 / 给提交打分")
    ap.add_argument("--criteria", required=True, help="六阶段退出标准 JSON")
    ap.add_argument("--submission", help="要打分的提交文件；不给就只生成量表")
    ap.add_argument("--out", default="results", help="产物目录")
    ap.add_argument("--tag", help="打分产物标签，写出 score_<tag>.json")
    args = ap.parse_args(argv)

    criteria = load_criteria(Path(args.criteria))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.submission:
        rubric = build_rubric(criteria)
        dest = out_dir / "rubric.json"
        dest.write_text(json.dumps(rubric, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        phases = "、".join(p["name"] for p in rubric["phases"])
        print(f"rubric_items={len(rubric['items'])} phases={phases} -> {dest}")
        return 0

    sub = Path(args.submission)
    if not sub.exists():
        print(f"打分失败：找不到提交文件 {sub}", file=sys.stderr)
        return 2

    tag = args.tag or sub.stem
    result = score(criteria, sub)
    dest = out_dir / f"score_{tag}.json"
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verdict = "通过" if result["passed"] else "不通过"
    print(
        f"passed={str(result['passed']).lower()} 判定={verdict} "
        f"达标={result['met_count']}/{result['total_count']} 未达标={result['unmet_count']} -> {dest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
