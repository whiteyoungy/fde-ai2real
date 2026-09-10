#!/usr/bin/env python3
"""课件构建入口。

    python3 slides/build_slides.py            # 全部
    python3 slides/build_slides.py day1 day3  # 指定某几天
    python3 slides/build_slides.py quotes     # 只出宣讲版《FDE 十二条》

每天一个 dayN.py，导入即生成同目录下的 pptx。生成完自动跑一遍版式核算——
本机禁用了 LibreOffice，版式只能靠算，所以这一步不是可选的。
"""
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DAYS = ["day1", "day2", "day3", "day4", "day5", "quotes", "exec", "fivesix"]


def main():
    want = sys.argv[1:] or DAYS
    bad = []
    for d in want:
        f = HERE / (d + ".py")
        if not f.exists():
            print("跳过 %s：%s 还没写" % (d, f.name))
            continue
        r = subprocess.run([sys.executable, str(f)], cwd=str(HERE))
        if r.returncode:
            bad.append(d)
    if bad:
        print("\n生成失败：%s" % "、".join(bad))
        return 1
    print()
    return subprocess.run([sys.executable, str(HERE / "check_layout.py")],
                          cwd=str(HERE)).returncode


if __name__ == "__main__":
    sys.exit(main())
