# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""验收辅助：读 results/ 产出，按 verify.sh 需要的口径打分。

用法（均由 verify.sh 调用，输出格式必须严格匹配它的判定逻辑，见该文件注释）：
    python3 -m src.check_results --out results --manifest fixtures/expected/manifest.json --mode classify
    python3 -m src.check_results --out results --manifest fixtures/expected/manifest.json --mode quarantine
    python3 -m src.check_results --out results --manifest fixtures/expected/manifest.json --mode fields
    python3 -m src.check_results --out results --manifest fixtures/expected/manifest.json --mode schema
    python3 -m src.check_results --out results --mode retries
"""
from __future__ import annotations

import argparse
import json
import pathlib

from .schema import InvoiceExtraction, ValidationError


def load_records(out_dir: pathlib.Path) -> dict[str, dict]:
    records_dir = out_dir / "records"
    records = {}
    if not records_dir.is_dir():
        return records
    for f in sorted(records_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records[d.get("file", f.stem)] = d
    return records


def load_manifest(path: str) -> list[dict]:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _floats_close(a, b, tol: float = 0.01) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def mode_classify(records: dict, manifest: list[dict]) -> str:
    """每条 manifest 记录：预测归类（clean→pass / quarantine→quarantine）与 outcome 是否一致。"""
    total = len(manifest)
    correct = 0
    for m in manifest:
        rec = records.get(m["file"])
        predicted = "pass" if (rec and rec.get("status") == "clean") else "quarantine"
        if predicted == m["outcome"]:
            correct += 1
    return f"{correct}/{total}"


def mode_quarantine(records: dict, manifest: list[dict]) -> str:
    """manifest 里标 quarantine 的几条，是否全部真的进了隔离队列（未混入 clean）。"""
    entries = [m for m in manifest if m["outcome"] == "quarantine"]
    correct = sum(1 for m in entries if records.get(m["file"], {}).get("status") == "quarantine")
    return f"{correct}/{len(entries)}"


def mode_fields(records: dict, manifest: list[dict]) -> str:
    """manifest 里标 pass 的几条，字段值是否与 expect 完全一致（有 key 严格模式）。"""
    entries = [m for m in manifest if m["outcome"] == "pass"]
    correct = 0
    for m in entries:
        rec = records.get(m["file"])
        if not rec or rec.get("status") != "clean" or not rec.get("fields"):
            continue
        exp, got = m["expect"], rec["fields"]
        ok = (
            str(got.get("invoice_no")) == exp["invoice_no"]
            and str(got.get("invoice_date")) == exp["invoice_date"]
            and _floats_close(got.get("amount_excl_tax"), exp["amount_excl_tax"])
            and _floats_close(got.get("tax_amount"), exp["tax_amount"])
            and _floats_close(got.get("total"), exp["total"])
        )
        if ok:
            correct += 1
    return f"{correct}/{len(entries)}"


def mode_schema(records: dict, manifest: list[dict]) -> str:
    """manifest 里标 pass 的几条，输出是否符合 schema（无 key 降级模式，不要求值正确）。"""
    entries = [m for m in manifest if m["outcome"] == "pass"]
    correct = 0
    for m in entries:
        rec = records.get(m["file"])
        if not rec or rec.get("status") != "clean" or not rec.get("fields"):
            continue
        try:
            InvoiceExtraction(**rec["fields"])
        except (ValidationError, TypeError, ValueError):
            continue
        correct += 1
    return f"{correct}/{len(entries)}"


def mode_retries(out_dir: pathlib.Path) -> str:
    """统计 retries.jsonl 里"校验失败→回灌→重试"事件的总次数。"""
    p = out_dir / "retries.jsonl"
    if not p.exists():
        return "0 次自纠错回灌（未发现 retries.jsonl）"
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return f"{len(lines)} 次校验失败后回灌重试（详见 {p}）"


def main() -> int:
    parser = argparse.ArgumentParser(description="按 verify.sh 需要的口径给 results/ 打分")
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest", required=False)
    parser.add_argument(
        "--mode", required=True, choices=["classify", "quarantine", "fields", "schema", "retries"]
    )
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)

    if args.mode == "retries":
        print(mode_retries(out_dir))
        return 0

    if not args.manifest:
        print("此 mode 需要 --manifest", flush=True)
        return 1

    records = load_records(out_dir)
    manifest = load_manifest(args.manifest)

    fn = {
        "classify": mode_classify,
        "quarantine": mode_quarantine,
        "fields": mode_fields,
        "schema": mode_schema,
    }[args.mode]
    print(fn(records, manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
