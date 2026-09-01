# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""脏 PDF 发票摄取管道入口。

用法：
    python3 -m src.run_pipeline --input fixtures/pdfs --out results

对每份 PDF：
    1. 抽文本（pdf_text.py）+ 归一化（textutil.py）
    2. 确定性规则先筛一道：文本为空/过短（截断文件、扫描件）直接隔离，
       不调用模型（rules.py::empty_text_reason）
    3. 正则抠一版候选草稿（rules.py::parse_draft），作为 prompt 提示 +
       模型多轮失败后的兜底候选
    4. 模型抽取 → Pydantic 强制校验 + grounding 校验 → 失败回灌重试
       （extractor.py），最多 MAX_ATTEMPTS 轮
    5. 模型始终没通过：再试一次用纯规则草稿本身过校验；能过就采用
       （标记 source=rule_fallback，明示"这条是规则兜底出的，不是模型给的"）；
       过不了就隔离，隔离原因带上最后一轮的校验错误
    6. 每个文件的完整记录写到 results/records/<stem>.json；
       每一次"回灌重试"事件追加写到 results/retries.jsonl，
       供 check_results.py --mode retries 统计"自纠错确实发生过几次"。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from .extractor import extract_with_self_correction
from .llm_client import default_client
from .pdf_text import extract_text
from .rules import empty_text_reason, parse_draft
from .schema import GroundingError, InvoiceExtraction, ValidationError, check_grounding
from .textutil import flatten_for_grounding, normalize

MAX_ATTEMPTS = 3


def process_one(path: pathlib.Path, client, retries_fp) -> dict:
    name = path.name
    raw_text, extract_err = extract_text(path)
    norm = normalize(raw_text) if raw_text else ""
    text_chars = len(norm.strip())

    reason = extract_err or empty_text_reason(norm)
    if reason:
        return {
            "file": name,
            "status": "quarantine",
            "source": "rule",
            "text_chars": text_chars,
            "fields": None,
            "attempts": [],
            "reason": reason,
        }

    draft = parse_draft(norm)
    grounding_text = flatten_for_grounding(norm)

    def on_retry(attempt: int, prior_error: str) -> None:
        retries_fp.write(
            json.dumps(
                {"file": name, "attempt": attempt, "prior_error": prior_error, "ts": time.time()},
                ensure_ascii=False,
            )
            + "\n"
        )
        retries_fp.flush()

    fields, attempts, ok = extract_with_self_correction(
        client, norm, draft, grounding_text, MAX_ATTEMPTS, on_retry
    )
    if ok:
        return {
            "file": name,
            "status": "clean",
            "source": "llm",
            "text_chars": text_chars,
            "fields": fields,
            "attempts": attempts,
            "reason": None,
        }

    # 模型自纠错若干轮仍未通过：看看纯规则草稿本身能不能独立过同一套校验。
    # 能过才采用（草稿必须自己扎实，不是"随便凑合"）；过不了就真隔离。
    try:
        obj = InvoiceExtraction(**draft)
        rescued_fields = obj.model_dump()
        check_grounding(rescued_fields, grounding_text)
    except (ValueError, ValidationError, TypeError) as e:
        last_error = attempts[-1]["error"] if attempts else str(e)
        return {
            "file": name,
            "status": "quarantine",
            "source": "llm",
            "text_chars": text_chars,
            "fields": None,
            "attempts": attempts,
            "reason": f"经 {len(attempts)} 轮自纠错后仍未通过强类型校验：{last_error}",
        }

    return {
        "file": name,
        "status": "clean",
        "source": "rule_fallback",
        "text_chars": text_chars,
        "fields": rescued_fields,
        "attempts": attempts,
        "reason": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="脏 PDF 发票摄取管道")
    parser.add_argument("--input", required=True, help="PDF 输入目录")
    parser.add_argument("--out", required=True, help="结果输出目录")
    args = parser.parse_args()

    in_dir = pathlib.Path(args.input)
    out_dir = pathlib.Path(args.out)
    if not in_dir.is_dir():
        print(f"输入目录不存在：{in_dir}", file=sys.stderr)
        return 1

    records_dir = out_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    retries_path = out_dir / "retries.jsonl"
    if retries_path.exists():
        retries_path.unlink()

    client = default_client()
    print(f"模型：{client.config.model}（{client.config.base_url}）")

    pdfs = sorted(in_dir.glob("*.pdf"))
    if not pdfs:
        print(f"输入目录里没有 PDF：{in_dir}", file=sys.stderr)
        return 1

    n_clean = n_quarantine = 0
    with open(retries_path, "a", encoding="utf-8") as retries_fp:
        for p in pdfs:
            print(f"处理 {p.name} ...")
            try:
                record = process_one(p, client, retries_fp)
            except Exception as e:  # 任何单个文件的意外故障都不能拖垮整条流水线
                record = {
                    "file": p.name,
                    "status": "quarantine",
                    "source": "error",
                    "text_chars": 0,
                    "fields": None,
                    "attempts": [],
                    "reason": f"处理过程中出现未预期异常：{type(e).__name__}: {e}",
                }
            (records_dir / f"{p.stem}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if record["status"] == "clean":
                n_clean += 1
                tag = f"clean/{record['source']}"
            else:
                n_quarantine += 1
                tag = f"quarantine：{record['reason']}"
            print(f"  -> {tag}")

    print(f"完成：{n_clean} 份 clean，{n_quarantine} 份 quarantine，共 {len(pdfs)} 份")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
