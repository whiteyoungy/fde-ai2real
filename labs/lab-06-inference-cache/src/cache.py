# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""三层语义缓存。

    第 1 层  稠密相似度   一次 embedding    负责**召回**：改写、同义、语序变化
    第 2 层  标识符护栏   免费（正则）      负责**分辨**：BX-07 / BX-70 这类
    第 3 层  模型裁判     一次短推理        负责剩下的纯语义分辨：公章 / 合同章

顺序不能换。第 2 层免费，必须排在花钱的第 3 层前面；第 1 层的相似度筛掉了
绝大多数候选，第 3 层因此只在极少数请求上付一次推理成本。

为什么必须分层，README 的表已经证明：这份夹具上应命中的最低相似度 0.651，
不该命中的最高 0.954（「合同盖公章找谁」/「合同盖合同章找谁」），两组完全
重叠——**不存在任何单一阈值能把它们分开**。这不是模型不好，是「语义相似」
和「能用同一个答案回复」本来就是两件事。

误命中的危害与检索失败完全不同：检索失败表现为「没找到」，误命中表现为一个
流畅、自信、完全错误的回答，而日志里缓存命中率还很好看。所以第 3 层的判定
方向是刻意偏保守的——**宁可少命中，不可错命中**。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import numpy as np

from . import common

# ── 第 3 层：裁判 ────────────────────────────────────────────────────────
JUDGE_ENDPOINT = os.environ.get(
    "DEEPSEEK_ENDPOINT", "https://api.deepseek.com/chat/completions"
)
JUDGE_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# 这段 prompt 是实测出来的，不要「优化」它。
#
# 关键是把「什么算不等价」逐条列出来，而不是笼统地说「判断是否相似」。
# 实测 deepseek-chat 在本夹具上 7/8，四条最难的「否」全对；唯一的错是把
# 「试用期多长」/「试用期一般是多久」判成了「否」。
#
# **那个方向的错是安全的**：把真同义判成不等价，代价只是多跑一次完整生成；
# 把不同义判成等价，代价是把别人问题的答案发给这个用户。为了修那一条而放松
# 措辞，会把「公章 / 合同章」这类误命中放回来。不要修。
#
# 另一条实测结论对第 7 章的 LLM-as-Judge 是个补充：裁判任务有模型尺寸下限。
# 本地 qwen2.5:0.5b 在六条测试上**全答「是」**，准确率 3/6 —— 它不是判错，
# 是根本没在判，输出是个常量。小模型跑通了不等于能当裁判。
JUDGE_SYSTEM = (
    "你是缓存等价性裁判。判断两个问题是否问的同一件事、"
    "能否用完全相同的答案回复。只回答「是」或「否」。"
    "涉及不同单据编号、不同费用科目、不同假期类型、不同印章，"
    "或一个问「是什么」另一个问「能不能改」的，都算否。"
)

JUDGE_TIMEOUT = float(os.environ.get("JUDGE_TIMEOUT", "30"))
JUDGE_RETRIES = 3


class JudgeError(RuntimeError):
    pass


def judge_available() -> bool:
    """key 只从环境变量读，永远不落盘、不进日志、不写进任何文件。"""
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def _judge_call(question_a: str, question_b: str) -> bool:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise JudgeError("DEEPSEEK_API_KEY 未设置")
    payload = {
        "model": JUDGE_MODEL,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"问题A：{question_a}\n问题B：{question_b}"},
        ],
        "temperature": 0,
        "max_tokens": 4,
        "stream": False,
    }
    req = urllib.request.Request(
        JUDGE_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    last: Exception | None = None
    for attempt in range(JUDGE_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=JUDGE_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = (data["choices"][0]["message"]["content"] or "").strip()
            # 只认「是」。空串、解释性长句、超时后的兜底——全部按「否」处理，
            # 因为「否」的代价是多一次推理，「是」的代价是发错答案。
            return text.startswith("是")
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as exc:
            last = exc
            if attempt < JUDGE_RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
    raise JudgeError(f"裁判调用失败（重试 {JUDGE_RETRIES} 次）：{last}")


# ── 缓存本体 ────────────────────────────────────────────────────────────
@dataclass
class Decision:
    """一次查询的完整判定轨迹。命中与否、卡在哪一层、相似度多少。"""

    hit: bool
    answer: str | None = None
    matched: str | None = None
    score: float = 0.0
    stage: str = "no_candidate"  # no_candidate|below_threshold|guard|judge|hit
    judged: bool = False


@dataclass
class Stats:
    lookups: int = 0
    hits: int = 0
    misses: int = 0
    blocked_by_guard: int = 0
    blocked_by_judge: int = 0
    judge_calls: int = 0
    stage_ms: dict[str, float] = field(default_factory=dict)

    def add(self, stage: str, ms: float) -> None:
        self.stage_ms[stage] = self.stage_ms.get(stage, 0.0) + ms


class SemanticCache:
    """进程内字典缓存。

    生产上这一层要换成 Redis / GPTCache——缓存必须跨实例共享，否则每个 pod
    各存一份，命中率被实例数除一遍。换存储不影响三层判定逻辑。
    """

    def __init__(
        self,
        threshold: float = common.SIM_THRESHOLD,
        use_guard: bool = True,
        use_judge: bool = True,
    ) -> None:
        self.threshold = threshold
        self.use_guard = use_guard
        # 没有 key 就没有第 3 层。这不是「降级也能用」，是**这个配置不安全**：
        # README 的数据已证明纯 embedding 在本夹具上任何阈值都做不到零误命中。
        self.use_judge = use_judge and judge_available()
        self.keys: list[str] = []
        self.answers: list[str] = []
        self._vecs: list[np.ndarray] = []
        self.stats = Stats()
        # 同一对问题的等价性判定是确定的（temperature=0），进程内记一次。
        # 这里记的是**裁判对某一对问题的判定**，不是「查询命中与否」的结论：
        # 缓存条目变了、候选换了，就是另一个 (key, query) 组合，会重新判。
        # 评测里每对用例都是全新的 SemanticCache + 单条目 + 单次查询，
        # 这个记忆永远命不中，因此第 3、4、5 项验收不受它影响。
        self._verdicts: dict[tuple[str, str], bool] = {}

    # ── 写入 ────────────────────────────────────────────────────────
    def put(self, question: str, answer: str) -> None:
        self.keys.append(question)
        self.answers.append(answer)
        self._vecs.append(common.encode_one(question))

    # ── 查询 ────────────────────────────────────────────────────────
    def lookup(self, question: str) -> Decision:
        self.stats.lookups += 1
        if not self.keys:
            self.stats.misses += 1
            return Decision(hit=False, stage="no_candidate")

        # 第 1 层：稠密召回。向量已 L2 归一化，点积即余弦。
        # 查询侧一律现算 embedding（use_cache=False）：线上每条进来的问题
        # 都要付这一次编码，用磁盘缓存替它等于把压测结果做假。
        t0 = time.perf_counter()
        qv = common.encode_one(question, use_cache=False)
        sims = np.stack(self._vecs) @ qv
        order = np.argsort(-sims)
        self.stats.add("embed", (time.perf_counter() - t0) * 1000.0)

        best_score = float(sims[order[0]])
        if best_score < self.threshold:
            self.stats.misses += 1
            return Decision(hit=False, score=best_score, stage="below_threshold")

        # 阈值之上可能不止一个候选。逐个过第 2、3 层，谁先过谁命中。
        blocked_at = "below_threshold"
        for idx in order:
            score = float(sims[idx])
            if score < self.threshold:
                break
            key = self.keys[idx]

            # 第 0 层：字符串完全相等直接放行，不跑护栏也不跑裁判。
            # 一模一样的两句话不需要任何模型来判断它们是不是一件事。
            # 少了这一条，压测里每个「标准问法」的重复请求都会白付一次裁判
            # 推理（实测 7 次 × 约 1.3 秒），P95 直接被顶回未命中的量级——
            # 生产上语义缓存前面几乎总还有一层精确哈希缓存，就是为了这个。
            if key == question:
                self.stats.hits += 1
                return Decision(
                    hit=True,
                    answer=self.answers[idx],
                    matched=key,
                    score=score,
                    stage="exact",
                )

            # 第 2 层：标识符护栏。免费，先跑。
            # 实测把误命中从 4 降到 2 而命中率不变——这种层就该无条件加上。
            # 它降不到零：f01（试用期是几个月 / 可以延长几个月）与
            # f11（公章 / 合同章）里没有编号可比，得靠第 3 层。
            if self.use_guard:
                t1 = time.perf_counter()
                conflict = common.ids_conflict(key, question)
                self.stats.add("guard", (time.perf_counter() - t1) * 1000.0)
                if conflict:
                    self.stats.blocked_by_guard += 1
                    blocked_at = "guard"
                    continue

            # 第 3 层：模型裁判。只在前两层都放行的候选上跑，一次短推理。
            judged = False
            if self.use_judge:
                judged = True
                pair = (key, question)
                if pair in self._verdicts:
                    equivalent = self._verdicts[pair]
                else:
                    t2 = time.perf_counter()
                    equivalent = _judge_call(key, question)
                    self.stats.add("judge", (time.perf_counter() - t2) * 1000.0)
                    self.stats.judge_calls += 1
                    self._verdicts[pair] = equivalent
                if not equivalent:
                    self.stats.blocked_by_judge += 1
                    blocked_at = "judge"
                    continue

            self.stats.hits += 1
            return Decision(
                hit=True,
                answer=self.answers[idx],
                matched=key,
                score=score,
                stage="hit",
                judged=judged,
            )

        # blocked_at 记的是**实际拦下它的那一层**。护栏排在裁判前面，f04/f07
        # 这种编号冲突的用例根本走不到裁判——把它们记成 "judge" 会让读者
        # 以为护栏没用、是裁判在兜底，正好搞反了本 Lab 要证明的事。
        self.stats.misses += 1
        return Decision(hit=False, score=best_score, stage=blocked_at)

    @property
    def mode(self) -> str:
        if not self.use_guard and not self.use_judge:
            return "naive"
        return "api" if self.use_judge else "nokey"
