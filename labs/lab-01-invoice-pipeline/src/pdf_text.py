# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""PDF 文本抽取。

可替换项：这里用 `pdftotext -layout` 做主抽取、PyMuPDF(fitz) 做兜底。
换成别的解析器（比如 pdfplumber，或接入真正的 OCR 处理扫描件）只需要
改这一个文件——只要 `extract_text()` 的签名 `(path) -> (text, error)`
不变，管道其余部分不用动。
"""
from __future__ import annotations

import pathlib
import subprocess


def extract_text(path: pathlib.Path) -> tuple[str, str | None]:
    """抽取 PDF 文本层。

    返回 (text, error)：
    - error 非空表示解析器认为文件本身有结构性问题（比如被截断），
      这类情况即使 text 里混进了半份内容也不可信，管道应直接隔离。
    - error 为空但 text 为空/极短，表示文件结构正常但没有文本层
      （典型是扫描件），同样应该隔离，但原因不同——不应该把空字符串
      喂给模型让它去"编"。这两种情况在 run_pipeline 里用同一个阈值判断
      合并处理，但保留各自的 error/reason 文案方便排查。
    """
    text, err = _try_pdftotext(path)
    if err is None and text.strip():
        return text, None

    # pdftotext 失败或抽出空文本，都用 fitz 再确认一次：
    # 有的文件 pdftotext 认为结构异常，但 fitz 仍能读出部分/全部文本层；
    # 也有可能两者一致地读出空文本（比如扫描件），此时保留更详细的错误信息。
    fitz_text, fitz_err = _try_fitz(path)
    if fitz_err is None and fitz_text.strip():
        return fitz_text, None

    # 两条路径都没有拿到可用文本：优先报告结构性错误（更利于排查），
    # 否则说明就是"结构正常但没有文本层"。
    return "", err or fitz_err


def _try_pdftotext(path: pathlib.Path) -> tuple[str, str | None]:
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return "", f"pdftotext 调用失败：{e}"
    if proc.returncode != 0:
        partial_stdout = proc.stdout.decode("utf-8", errors="replace")  # 通常是空，防御性保留
        stderr_msg = proc.stderr.decode("utf-8", errors="replace").strip()
        first_line = stderr_msg.splitlines()[0] if stderr_msg else f"exit={proc.returncode}"
        return partial_stdout, f"pdftotext 报错（PDF 结构异常）：{first_line}"
    return proc.stdout.decode("utf-8", errors="replace"), None


def _try_fitz(path: pathlib.Path) -> tuple[str, str | None]:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:  # pragma: no cover - 环境已确认装了 fitz
        return "", f"fitz 未安装：{e}"
    try:
        doc = fitz.open(str(path))
        parts = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(parts), None
    except Exception as e:  # PyMuPDF 对损坏文件抛的异常类型不固定
        return "", f"fitz 解析异常（PDF 结构异常）：{e}"
