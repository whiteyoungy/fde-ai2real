# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""verify.sh [3/5]：LLM-as-Judge 偏差缓解自检（成对比较 + 顺序打乱，对应第 7.4 节）。

第 7.4 节讲的位置偏差缓解手段落到 `scorers.py` 里是两个函数：
- `llm_pairwise_judge`：不显式指定 order 时随机打乱两个候选答案的呈现顺序——
  这就是"打乱顺序"这一缓解手段本身。
- `pairwise_consistency_check`：同一对答案正序（A,B）判一次、反序（B,A）判一次，
  两次结论是否一致，就是判断这次判断有没有被呈现顺序左右——这是"成对比较"用来
  检测/缓解位置偏差的标准做法。

本自检验证这两者都真的在起作用，按 README「验收标准」一节分两档：

- 有 `DEEPSEEK_API_KEY`：验证真实判别力。裁判模型要能在一个明显忠实于知识库的答案
  和一个明显编造事实的答案之间，正确且一致地（正序、反序都一样）选出忠实的那个——
  一致，说明这次判断没有被位置偏差污染。
- 无 key（降级 `qwen2.5:0.5b`）：模型太弱，不要求它判断正确或前后一致，只要求机制
  本身跑通——调用不抛异常、能从裁判输出里解析出一个胜者标签、顺序打乱这个机制本身
  确实在起作用（多次调用里 ["A","B"] 和 ["B","A"] 两种呈现顺序都出现过）。
"""
from __future__ import annotations

import sys

from src.llm_client import default_client, has_key
from src.scorers import llm_pairwise_judge, pairwise_consistency_check

CHECKS_RUN = 0

# 取自 datasets/golden.jsonl golden-0001 对应的 kb-001，退款政策问答场景。
QUESTION = "订单超过7天了，还可以无理由退款吗？"
FAITHFUL_ANSWER = "订单超过7天后原则上不支持无理由退款，但商品存在质量问题时依然可以申请退款。"
FABRICATED_ANSWER = "订单超过7天依然可以无理由退款，并且平台会额外补偿100元现金。"


def check(label: str, condition: bool) -> None:
    global CHECKS_RUN
    CHECKS_RUN += 1
    if not condition:
        raise AssertionError(f"自检失败: {label}")


def _check_shuffle_mechanism() -> None:
    """机制检查，不依赖模型：多次调用 llm_pairwise_judge 不传 order，
    呈现顺序应该在 ["A","B"] 和 ["B","A"] 之间随机分布。

    chat_fn 用一个固定返回"1"的桩函数——这里要测的是"顺序有没有被打乱"这个机制
    本身，不是模型的判断能力，所以不需要真的打模型。
    """
    orders_seen = {
        tuple(llm_pairwise_judge(lambda _: "1", QUESTION, "x", "y")["presented_order"])
        for _ in range(20)
    }
    # 20 次里两种顺序都没出现的概率是 0.5**20，实际上不可能发生，可以放心断言。
    check("顺序打乱机制生效（多次调用呈现顺序具备随机性）", len(orders_seen) == 2)


def main() -> int:
    try:
        _check_shuffle_mechanism()

        client = default_client()
        result = pairwise_consistency_check(
            client.chat, QUESTION, FAITHFUL_ANSWER, FABRICATED_ANSWER
        )

        check("成对比较正序调用未抛异常且能解析出胜者", result["winner_ab_order"] is not None)
        check("成对比较反序调用未抛异常且能解析出胜者", result["winner_ba_order"] is not None)

        if has_key():
            # 有 key：验证真实判别力。
            check("真实裁判正序判给更忠实的答案", result["winner_ab_order"] == "A")
            check("真实裁判反序仍判给更忠实的答案", result["winner_ba_order"] == "A")
            check("真实裁判正反序结论一致（位置偏差缓解生效）", result["consistent"])
        else:
            # 无 key：qwen2.5:0.5b 当裁判基本不可用，只验证机制跑通，
            # 不对判断的正确性/一致性做要求。
            print(
                "无 DEEPSEEK_API_KEY，降级为机制自检模式："
                "不要求 qwen2.5:0.5b 判断正确或正反序一致，只要求成对比较调用能跑通并解析出胜者。",
                file=sys.stderr,
            )

    except AssertionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    mode = "真实判别力" if has_key() else "机制自检"
    print(f"{CHECKS_RUN} 项断言全部通过（{mode}模式）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
