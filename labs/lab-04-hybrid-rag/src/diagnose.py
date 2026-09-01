# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""三分法归因：把"回答不对"拆成四种根因，各自对应完全不同的修法。

    Step 1  知识库里有支持材料吗   ── 否 → missing_content      （补内容）
    Step 2  这份材料出现在检索结果里吗 ── 否 → retrieval_failure （修检索）
    Step 2b 命中的材料内容本身对吗 ── 否 → data_pollution        （治理数据）
    Step 3  回答忠实于 context 吗  ── 否 → hallucination         （改提示词/换模型）
                                    ── 是 → answer_actually_correct（什么都别改）

最后那一档最容易被忽略。诊断脚本必须能对"本来就是对的"回答保持沉默，
否则它每次都报故障，整套归因就没有信息量了。

用法：
  python3 -m src.diagnose --qdrant URL --cases fixtures/diagnose_cases.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
from collections import Counter

from . import common
from .index import build_client
from .retrieve import Retrievers, scroll_all

CONTEXT_K = 5          # 送进模型的 context 深度，与 Recall@5 对齐

# ── Step 1 的判据阈值 ────────────────────────────────────────────
# 两个信号取或：任一成立就认为"知识库里有这份材料"。
# 只用其中一个都会翻车，这是实测出来的：
#   · 只用字级覆盖：dg-5「辞职之前要交接哪些东西」只剩 辞/职/交/接 四个内容字，
#     其中 交/接 在语料里几乎人人都有，覆盖率被摊到 0.45，比真正没材料的
#     dg-1（0.38）高不了多少。
#   · 只用词级证据：dg-4「没休完的年假第二年还能用吗」里 没休/年假/第二年
#     在语料中一个都不存在（文档写的是「年休假」「结转」），词级证据近乎为零。
# 两个信号覆盖的是两种不同的表述差距，所以取或而不是取与。
#
# 实测到的两路信号取值（49 个模板为基数）：
#            词级证据   字级覆盖率
#   dg-1        7.1        0.321      ← 真的没材料
#   dg-3       18.1        0.597
#   dg-4        4.7        0.752
#   dg-5       33.5        0.140
# 阈值取在两侧留出倍数级余量的位置。这两个数是对着本 Lab 语料标定的，
# 换语料必须重标——真实项目里这一步通常交给 LLM 或人，而不是阈值。
RARE_DF_FRAC = 0.25    # "稀有词"上限：出现在不超过 25% 模板里的词才算证据
CHAR_MIN = 0.60        # 字级 IDF 覆盖率下限
TERM_MIN = 12.0        # 词级稀有词证据下限（IDF 之和）
FAITHFUL_MIN = 0.70    # Step 3 降级档：回答被 context 覆盖的比例下限

_STOP = set("""
的 了 是 在 有 和 就 不 都 也 很 到 说 要 去 你 我 他 她 它 们 吗 呢 吧 啊 么
什么 怎么 哪些 哪个 多少 多久 可以 能 还 又 才 被 把 给 让 从 对 与 及 等 之
前 后 里 中 内 外 时候 个 东西 该 其 此 为 以 于 而 且 或 但 如果 因 所 然后
再 各 按 需 上 下 会 着 好 这 那 样 过 将 并 只 使 得 另 同 已经 一个 每 种 做
作 出来 自 向 由于 当 上次 那个 好像 一下 一些 需要 是否 包括 进行 相关 通过
以及 其中 没有 都行 一 二 三 四 五 六 七 八 九 十 元 万元 以内 之前 之后
""".split())


# ── 语料统计：先按模板去重，再算词权重 ───────────────────────────
class Lexicon:
    """字/词的文档频率统计。

    **先去重再统计**：1200 篇复盘报告只有编号不同，正文一模一样。
    直接按 1241 篇算 IDF，会把"交接""改进""补充"这些在模板里出现的词
    压到权重 0，而把「第」「二」这种功能字抬成高权重词——IDF 被同质文档海
    毒化了。抹掉标识符后按正文去重，1241 篇塌成 49 个模板，权重才有意义。
    """

    def __init__(self, texts: list[str]):
        seen, uniq = set(), []
        for t in texts:
            key = common.ID_RE.sub("", t).lower()
            if key not in seen:
                seen.add(key)
                uniq.append(key)
        self.n = max(1, len(uniq))
        self.uniq = uniq
        self.char_df = Counter()
        for t in uniq:
            self.char_df.update(set(t))

    def char_idf(self, ch: str) -> float:
        return math.log(self.n / (1 + self.char_df.get(ch, 0)))

    def term_df(self, term: str) -> int:
        return sum(1 for t in self.uniq if term in t)


def _content_chars(text: str) -> list[str]:
    """查询里真正携带内容的汉字。数字/字母交给标识符扫描那一路。"""
    return [c for c in dict.fromkeys(text)
            if not (c in common._PUNCT or c.isascii() or c in _STOP)]


def _terms(text: str) -> list[str]:
    import jieba
    out = []
    for t in jieba.lcut(text.lower()):
        t = t.strip()
        if len(t) >= 2 and t not in _STOP and not t.isascii() \
                and not all(c in common._PUNCT for c in t):
            out.append(t)
    return list(dict.fromkeys(out))


# ── Step 1 ───────────────────────────────────────────────────────
def step1_scan(payloads: list[dict], lex: Lexicon,
               query: str, answer: str) -> tuple[set[str], dict]:
    """知识库里到底有没有这份材料。

    走 scroll() 拿到的**全量 payload**做精确扫描，刻意不碰 query_points()。
    这一步要确认的是"内容存在与否"这个更底层的事实：如果这里也走向量检索，
    dg-2 那种"文档在库里、只是检索捞不到"的情况会被误判成 missing_content，
    整个三分法就退化成"检索说没有就是没有"，一点信息都没多出来。
    """
    texts = {p["doc_id"]: (p["title"] + "\n" + p["body"]).lower() for p in payloads}

    # 信号 A：标识符精确命中。有它就是决定性证据，不再看别的——
    # 查询里写了 INC-20777，用户指的就是那一篇，语义相似度说什么都不算数。
    q_ids = set(common.extract_ids(query)) | set(common.extract_ids(answer))
    if q_ids:
        hits = {p["doc_id"] for p in payloads
                if q_ids & set(p.get("codes") or ())}
        if hits:
            return hits, {"signal": "exact-id", "ids": sorted(q_ids),
                          "n_docs": len(hits)}

    # 信号 B：词级稀有词证据（query + answer）。
    # 带上 answer 是因为真实排障里"回答复述的说法能不能在库里原样找到"
    # 本身就是最强的存在性证据——dg-5 的回答几乎逐字引自 d-sem-05。
    rare = {}
    cap = max(2, int(RARE_DF_FRAC * lex.n))
    for t in _terms(query + " " + answer):
        d = lex.term_df(t)
        if 0 < d <= cap:
            rare[t] = math.log(lex.n / d)
    term_score = {did: sum(w for t, w in rare.items() if t in tx)
                  for did, tx in texts.items()}
    term_best = max(term_score.values(), default=0.0)

    # 信号 C：字级 IDF 覆盖率（只看 query）。
    # 不带 answer：回答可能是幻觉，拿它算覆盖率会自证清白。
    cs = _content_chars(query)
    cw = {c: lex.char_idf(c) for c in cs}
    ctot = sum(cw.values()) or 1.0
    char_cov = {did: sum(w for c, w in cw.items() if c in tx) / ctot
                for did, tx in texts.items()}
    char_best = max(char_cov.values(), default=0.0)

    support: set[str] = set()
    if term_best >= TERM_MIN:
        support |= {d for d, s in term_score.items() if s >= 0.8 * term_best}
    if char_best >= CHAR_MIN:
        support |= {d for d, s in char_cov.items() if s >= 0.95 * char_best}

    return support, {"signal": "lexical-scan",
                     "term_best": round(term_best, 2),
                     "char_best": round(char_best, 3),
                     "n_docs": len(support)}


# ── Step 3 ───────────────────────────────────────────────────────
def _grounding(answer: str, context: str) -> float:
    """回答里的实词有多大比例能在 context 里找到。降级档的忠实度代理指标。"""
    ts = _terms(answer)
    if not ts:
        return 1.0
    low = context.lower()
    return sum(1 for t in ts if t in low) / len(ts)


# 「把材料里的限制条件抹掉」是 RAG 幻觉最典型的形态，也是最难被用户察觉的形态：
# 原文写「最多可结转至次年第一季度末」，回答写成「可以无限期结转」——
# 措辞专业、结构完整、和问题严丝合缝，只有逐条比对限定词才看得出来。
# 这类绝对化措辞如果在 context 里找不到出处，就是无中生有。
_ABSOLUTIZERS = ("无限期", "永久", "永远", "任何时候", "随时", "无需", "不需要",
                 "一律", "全都", "均可", "不限", "无上限", "没有限制", "不受限制",
                 "无条件", "自动延续", "都行", "都可以")


def _ungrounded_absolutizers(answer: str, context: str) -> list[str]:
    low = context.lower()
    return [w for w in _ABSOLUTIZERS if w in answer and w not in low]


def step3_faithful(answer: str, context: str) -> tuple[bool, str, str]:
    """回答是否忠实于 context。返回 (是否忠实, 档位, 理由)。

    有 DEEPSEEK_API_KEY 时用真实模型判定；没有就降级到可解释的规则。
    两条路径都要能过验收——降级档不是摆设，客户现场断网/没预算是常态，
    而"这套诊断离了外部 API 就跑不动"在交付评审上是过不了的。
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        verdict = _llm_faithful(key, answer, context)
        if verdict is not None:
            return verdict, "llm(deepseek)", "模型判定"

    bad = _ungrounded_absolutizers(answer, context)
    if bad:
        return (False, "heuristic(absolutizer+grounding)",
                f"回答出现 context 里没有的绝对化措辞 {bad}，限制条件被抹掉了")
    g = _grounding(answer, context)
    return (g >= FAITHFUL_MIN, "heuristic(absolutizer+grounding)",
            f"实词落地率 {g:.2f}（阈值 {FAITHFUL_MIN}），无绝对化措辞越界")


def _llm_faithful(key: str, answer: str, context: str) -> bool | None:
    """调 DeepSeek 判忠实度。任何异常都返回 None，让调用方降级——
    诊断工具不能因为外部 API 抖一下就整个跑不出结果。"""
    try:
        import httpx
        base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        prompt = (
            "你是 RAG 质量审计员。只依据【材料】判断【回答】是否忠实。\n"
            "忠实 = 回答的每一项事实都能在材料里找到依据，且没有夸大、"
            "没有把材料里的限制条件去掉。\n"
            "只输出一个词：FAITHFUL 或 UNFAITHFUL。\n\n"
            f"【材料】\n{context[:4000]}\n\n【回答】\n{answer}\n")
        r = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "deepseek-chat", "temperature": 0,
                  "max_tokens": 8,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=45.0)
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"].strip().upper()
        if "UNFAITHFUL" in out:
            return False
        if "FAITHFUL" in out:
            return True
        return None
    except Exception:
        return None


# ── 主流程 ───────────────────────────────────────────────────────
def diagnose_case(case: dict, retr: Retrievers, payloads: list[dict],
                  lex: Lexicon, by_id: dict[str, dict]) -> dict:
    query, answer = case["query"], case.get("answer", "")

    support, ev = step1_scan(payloads, lex, query, answer)
    if not support:
        return {"root_cause": "missing_content", "step": 1,
                "evidence": ev, "tier": "scroll-scan",
                "detail": "全库精确扫描没有找到能支持这个问题的材料，"
                          "补内容是唯一解——调检索参数、换 embedding 模型都没用"}

    # Step 2：用这条 case 指定的检索器，不要一律用混合。
    # dg-2 的意义就在于"纯向量捞不到"，换成混合就命中了，故障也就测不出来。
    kind = case.get("retriever", "hybrid")
    qvec = common.encode([query], "diagnose")[0]
    context_ids = retr.search(kind, query, qvec, common.TOPK)[:CONTEXT_K]
    hit = [d for d in context_ids if d in support]
    if not hit:
        return {"root_cause": "retrieval_failure", "step": 2,
                "evidence": {**ev, "retriever": kind, "context": context_ids,
                             "support_sample": sorted(support)[:5]},
                "tier": "scroll-scan",
                "detail": f"材料在库里（{len(support)} 篇），但 {kind} 检索的 "
                          f"top-{CONTEXT_K} 里一篇都没有——修检索，不修数据也不换模型"}

    # Step 2b：命中的材料内容本身对吗。
    # 判据是文档的 superseded_by 字段，不是看模型怎么转述它——
    # 被取代的旧规内容自洽、措辞专业，光看回答一辈子也看不出问题。
    # 注意只在 Step 1 认定的支持集里查：dg-4 的 hybrid top-5 里也躺着
    # d-stale-01，但它跟"年假结转"这个问题无关，不该算作污染。
    polluted = [d for d in hit if by_id[d].get("superseded_by")]
    if polluted:
        d = polluted[0]
        return {"root_cause": "data_pollution", "step": 2.5,
                "evidence": {**ev, "retriever": kind, "context": context_ids,
                             "stale": d,
                             "superseded_by": by_id[d]["superseded_by"]},
                "tier": "scroll-scan",
                "detail": f"检索命中的 {d} 已被 {by_id[d]['superseded_by']} 取代。"
                          "整条链路每一步看起来都正常，只有比对权威版本才露馅"}

    # Step 3：回答忠实于 context 吗。
    context = "\n\n".join(f"{by_id[d]['title']}\n{by_id[d]['body']}" for d in hit)
    faithful, tier, why = step3_faithful(answer, context)
    if faithful:
        return {"root_cause": "answer_actually_correct", "step": 3,
                "evidence": {**ev, "retriever": kind, "context": context_ids,
                             "grounded_on": hit},
                "tier": tier,
                "detail": f"三步全部正常，这条回答本来就是对的（{why}）。"
                          "诊断在这里必须闭嘴——乱报故障的诊断没有信息量"}
    return {"root_cause": "hallucination", "step": 3,
            "evidence": {**ev, "retriever": kind, "context": context_ids,
                         "grounded_on": hit},
            "tier": tier,
            "detail": f"材料在库、检索命中、内容也没过期，但回答没有忠实转述（{why}）"}


def run(qdrant: str, cases_path: pathlib.Path, collection: str,
        out: pathlib.Path | None) -> int:
    cases = common.load_jsonl(cases_path)
    client = build_client(qdrant)
    payloads = scroll_all(client, collection)
    lex = Lexicon([f"{p['title']}\n{p['body']}" for p in payloads])
    by_id = {p["doc_id"]: p for p in payloads}
    retr = Retrievers(client, collection)

    rows, correct = [], 0
    for c in cases:
        r = diagnose_case(c, retr, payloads, lex, by_id)
        ok = (r["root_cause"] == c["expect"])
        correct += ok
        rows.append({"id": c["id"], "expect": c["expect"], **r, "ok": ok})
        print(f"  {c['id']}  {'OK ' if ok else 'BAD'}  "
              f"got={r['root_cause']:<24} expect={c['expect']:<24} "
              f"step={r['step']} tier={r['tier']}")

    tiers = sorted({r["tier"] for r in rows})
    print(f"correct={correct} total={len(cases)} tiers={','.join(tiers)}")
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "diagnosis.json").write_text(
            json.dumps({"correct": correct, "total": len(cases), "cases": rows},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    return correct


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qdrant", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--collection", default=common.COLLECTION)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    run(args.qdrant, pathlib.Path(args.cases), args.collection,
        pathlib.Path(args.out) if args.out else None)


if __name__ == "__main__":
    main()
