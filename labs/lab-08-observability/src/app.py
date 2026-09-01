#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""被观测的流水线：检索 → 生成，全程埋点到 Langfuse。

    python3 -m src.app --ingest URL --cases fixtures/pii_cases.jsonl
    → traces=8 spans=24 generations=8

—— trace 该长成什么样 ——
一次业务动作 = 一条 trace，里面按真实步骤拆 span：

    answer_question           根 span，业务动作这一层
    ├── retrieve              检索，type=retriever
    └── llm_generate          生成，type=generation ← 成本挂在这一层

这样才能回答「这次回答慢在哪一步」。如果每步各建各的 trace，
拿到的是一堆孤立事件，排障时等于没埋点。
实现上靠 `@observe` 嵌套调用自动串父子关系，**不要在每步手动新建 trace**。

—— 脱敏挂在哪 ——
`_span_io()` / `_generation_io()` 是本模块**唯一**写 span 属性的地方，
脱敏就挂在这两个函数里。原文只存在于 `run_case()` 的局部变量 `raw` 中，
任何要跨出进程的路径都得先过 `redact()`：

    · 进 span 属性      → _span_io / _generation_io
    · 进检索索引        → retrieve() 收到的已是脱敏文本（持久化存储同样受限）
    · 发给模型厂商 API  → _call_llm() 收到的已是脱敏文本
    · 异常信息          → _safe_error()，异常消息里的原文照样会被 SDK 上报

第 13 章原文：「脱敏后的日志才允许写入持久化存储或转发给 Langfuse——
这一步顺序不能反。」顺序反了不是「日志里有敏感信息」这么轻，是**你把客户的
个人信息发给了第三方 SaaS，发出去就收不回来**。

—— 一个容易漏的坑 ——
`@observe` 默认会自动捕获函数入参和返回值写进 span（capture_input /
capture_output）。只要原文作为参数传进被装饰的函数，它就绕过了上面所有闸门
直接进了 span 属性。所以本模块所有 `@observe` 都显式关掉了自动捕获，
输入输出一律手工写、手工脱敏。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from langfuse import Langfuse, get_client, observe

from .redact import redact

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRICING = ROOT / "fixtures" / "pricing.json"

# ── 两档生成后端 ────────────────────────────────────────────────
# 有 key 走 deepseek-chat（真实 token 与真实成本），无 key 走本地 Ollama
# （token 为真、API 成本为 0）。两档共用同一套埋点代码，切换只换 _call_llm 的分支。
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"          # 必须与 pricing.json 的 models 键一致
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_TAG = "qwen2.5:0.5b"
OLLAMA_MODEL = "qwen2.5-0.5b-local"       # 同上
LLM_TIMEOUT = 120

# 迷你知识库。真实项目这里是向量库；本 Lab 用关键词打分，
# 因为磁盘只剩几个 G，装不下 embedding 模型——README「可替换组件」已注明。
KB = [
    {"id": "kb-01", "title": "报销到账时效",
     "text": "报销单提交后由财务在 3 个工作日内审核，审核通过后于次周二统一打款。"},
    {"id": "kb-02", "title": "入职材料清单",
     "text": "入职材料包含身份证明、学历证明与体检报告，人事在入职日期前一周收齐。"},
    {"id": "kb-03", "title": "工资卡变更",
     "text": "工资卡变更需在单据中提交新卡信息，变更在下一个发薪周期生效。"},
    {"id": "kb-04", "title": "发票开具",
     "text": "订单完成后可申请开票，电子发票在 2 个工作日内发送至预留邮箱。"},
    {"id": "kb-05", "title": "物流查询",
     "text": "快递单号可在承运商官网查询，异常件由客服在 24 小时内跟进。"},
    {"id": "kb-06", "title": "审批卡单处理",
     "text": "订单审批超过 48 小时未流转的，由值班主管介入并在工单中记录原因。"},
    {"id": "kb-07", "title": "错误码处理",
     "text": "错误码以 ERR- 开头，复现步骤需登记在工单中，由二线支持定位。"},
    {"id": "kb-08", "title": "成本报表口径",
     "text": "成本报表按季度出具，预算编号对应一个成本中心，超限需走追加预算流程。"},
]


# ── 信任边界上的闸门 ────────────────────────────────────────────
# 下面两个函数是本模块唯一写 span 属性的出口。要验证「脱敏确实在上报之前」，
# 只需要看这两个函数——这正是把闸门收敛到一处的意义。
# （README 延伸练习 3：把这里的 redact() 去掉，verify.sh 第 4 项必须立刻失败。
#   一个不会失败的检查等于没有这个检查。）

def _span_io(**fields: Any) -> None:
    """写普通 span 的属性。所有字段先过脱敏。"""
    payload = {k: redact(v) for k, v in fields.items() if v is not None}
    if payload:
        get_client().update_current_span(**payload)


def _generation_io(**fields: Any) -> None:
    """写 generation span 的属性。所有字段先过脱敏。

    model / usage_details 这类结构化字段本身不含 PII，但照样过一遍：
    闸门上开例外口子，就是下一次泄漏的来源。`redact()` 对 int/float 是恒等的，
    过一遍不会把 token 数改坏。
    """
    payload = {k: redact(v) for k, v in fields.items() if v is not None}
    if payload:
        get_client().update_current_generation(**payload)


def _safe_error(exc: BaseException) -> str:
    """把异常压成一行**已脱敏**的短消息。

    异常是最容易被忽略的泄漏路径：`ValueError(f"无法解析：{原文}")` 这种写法
    会把原文塞进 span 的异常事件里，而字段级检查完全看不到它——
    verify.sh 第 4 项在原始字节上搜，就是为了堵这个口子。
    """
    return redact(f"{type(exc).__name__}: {exc}")[:300]


# ── 流水线 ──────────────────────────────────────────────────────

@observe(name="retrieve", as_type="retriever", capture_input=False, capture_output=False)
def retrieve(safe_query: str, top_k: int = 2) -> list[dict]:
    """检索。入参已经是脱敏文本——检索索引也是持久化存储，同样在边界之外。"""
    scored = []
    for doc in KB:
        hit = sum(1 for ch in set(safe_query) if ch in doc["text"] or ch in doc["title"])
        scored.append((hit, doc))
    scored.sort(key=lambda x: -x[0])
    docs = [d for _, d in scored[:top_k]]
    _span_io(
        input=safe_query,
        output="；".join(f"{d['id']} {d['title']}" for d in docs),
        metadata={"kb_size": len(KB), "top_k": top_k},
    )
    return docs


def _call_llm(prompt: str) -> dict:
    """调用生成模型。prompt 已是脱敏文本。

    返回 {model, text, input_tokens, output_tokens}。token 数取自厂商返回体，
    不自己估算——成本看板一旦开始估 token，数字就没法和账单对上了。
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if api_key:
        body = {
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 160,
            "temperature": 0.2,
            "stream": False,
        }
        # key 只从环境变量读，绝不落盘、绝不进 span
        data = _post_json(DEEPSEEK_URL, body, {"Authorization": f"Bearer {api_key}"})
        usage = data.get("usage") or {}
        return {
            "model": DEEPSEEK_MODEL,
            "text": (data["choices"][0]["message"].get("content") or "").strip(),
            "input_tokens": int(usage.get("prompt_tokens", 0)),
            "output_tokens": int(usage.get("completion_tokens", 0)),
        }

    body = {
        "model": OLLAMA_TAG,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": 128, "temperature": 0.2},
    }
    data = _post_json(OLLAMA_URL, body, {})
    return {
        "model": OLLAMA_MODEL,
        "text": (data.get("message", {}).get("content") or "").strip(),
        "input_tokens": int(data.get("prompt_eval_count", 0)),
        "output_tokens": int(data.get("eval_count", 0)),
    }


def _post_json(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


@observe(name="llm_generate", as_type="generation", capture_input=False, capture_output=False)
def generate(safe_query: str, docs: list[dict], action: str, case_id: str) -> dict:
    """生成。标为 generation 类型，token 数与模型名挂在这一层——成本归因的落点。"""
    context = "\n".join(f"- {d['title']}：{d['text']}" for d in docs)
    prompt = (
        "你是企业内部客服助手。请依据下列资料，用一到两句中文回答用户问题。\n"
        f"资料：\n{context}\n\n用户问题：{safe_query}\n回答："
    )

    try:
        res = _call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        # 生成失败不能让整条 trace 消失——没有 trace 就等于没有排障线索。
        # 记一条已脱敏的错误，token 记 0，成本自然为 0。
        msg = _safe_error(exc)
        print(f"[warn] {case_id} 生成失败：{msg}", file=sys.stderr)
        _generation_io(
            input=prompt,
            output="",
            model=DEEPSEEK_MODEL if os.environ.get("DEEPSEEK_API_KEY") else OLLAMA_MODEL,
            usage_details={"input": 0, "output": 0},
            metadata={"business_action": action, "case_id": case_id, "llm_error": msg},
            level="ERROR",
            status_message=msg,
        )
        return {"text": "", "input_tokens": 0, "output_tokens": 0, "error": msg}

    _generation_io(
        input=prompt,
        output=res["text"],
        model=res["model"],
        usage_details={"input": res["input_tokens"], "output": res["output_tokens"]},
        metadata={"business_action": action, "case_id": case_id},
    )
    return res


def run_case(case: dict, action: str) -> bool:
    """一条用例 = 一次业务动作 = 一条 trace。返回生成是否成功。

    根 span 的名字就是业务动作名（answer_question / summarize_ticket /
    draft_reply），成本看板按它聚合。
    """
    ok = True

    @observe(name=action, capture_input=False, capture_output=False)
    def _traced() -> None:
        nonlocal ok
        raw = case["text"]          # 原文只在这个局部变量里存在
        safe = redact(raw)          # 过闸门，之后一律只用 safe

        _span_io(
            input=safe,
            metadata={"business_action": action, "case_id": case["id"],
                      "redacted": safe != raw},
        )
        try:
            docs = retrieve(safe)
            res = generate(safe, docs, action, case["id"])
            ok = not res.get("error")
            _span_io(output=res.get("text") or "(生成失败，见子 span)")
        except Exception as exc:  # noqa: BLE001
            ok = False
            _span_io(output="", level="ERROR", status_message=_safe_error(exc))
            raise RuntimeError(_safe_error(exc)) from None

    _traced()
    return ok


def load_actions(pricing_path: Path) -> list[str]:
    """业务动作取自 pricing.json 的 business_actions，不在代码里另写一份。

    看板的口径必须和单价表同源。两处各写一份，改了一处忘了另一处，
    看板就会悄悄漏掉一个动作而不报错。
    """
    with pricing_path.open(encoding="utf-8") as f:
        return list(json.load(f)["business_actions"].keys())


def main() -> int:
    ap = argparse.ArgumentParser(description="Lab-08 被观测的流水线")
    ap.add_argument("--ingest", required=True, help="Langfuse / mock 摄取端地址")
    ap.add_argument("--cases", required=True, help="用例 jsonl")
    ap.add_argument("--pricing", default=str(DEFAULT_PRICING), help="单价表（取业务动作定义）")
    args = ap.parse_args()

    cases = [json.loads(line) for line in Path(args.cases).open(encoding="utf-8") if line.strip()]
    actions = load_actions(Path(args.pricing))

    # 指向 mock 摄取端。真实 Langfuse 只需要换 host 与密钥，src/ 一行不用改——
    # 这正是把 mock 做在摄取端而不是 SDK 层的好处。
    lf = Langfuse(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-lab08"),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-lab08"),
        host=args.ingest,
        flush_at=1,
        tracing_enabled=True,
    )

    spans_per_trace = 3          # 根 + retrieve + generate
    failed = 0
    for i, case in enumerate(cases):
        if not run_case(case, actions[i % len(actions)]):
            failed += 1

    lf.flush()
    time.sleep(1.5)              # OTLP 是批量异步导出，flush 后还要等一下才落到摄取端

    print(f"traces={len(cases)} spans={len(cases) * spans_per_trace} "
          f"generations={len(cases)}")

    # 全部生成都失败时必须报错退出。
    # 这条不是给 verify.sh 用的——verify.sh 查不出这种情况：所有调用的
    # token 数都是 0，成本自然也是 0，「按单价表重算一致」照样成立，7 项全绿。
    # 换句话说，key 过期、Ollama 没起、网络不通这类故障，会以「验收通过」的
    # 形态呈现出来。看板上是一排 0，没人会觉得那是故障。
    # 所以这里自己把它喊出来，别让沉默的失败混过去。
    if failed and failed == len(cases):
        print(f"[error] {failed}/{len(cases)} 次生成全部失败，本次成本数据没有意义。"
              f"检查 DEEPSEEK_API_KEY 是否有效、或本地 Ollama（{OLLAMA_URL}）是否在跑。",
              file=sys.stderr)
        return 1
    if failed:
        print(f"[warn] {failed}/{len(cases)} 次生成失败，相应调用的 token 记 0。",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
