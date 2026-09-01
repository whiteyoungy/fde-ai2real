#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""证书轮换回归探针（verify.sh [7/7] 用）。

在持续对网关发起 ``GET /api/orders/A-7781`` 请求的同时，触发网关一次
客户端证书轮换（``POST /admin/rotate``），统计整个过程里有多少请求失败。
现场最容易出事的一步就是这里：切换瞬间连接池里可能还挂着用旧证书建立
的连接、正在飞行的请求可能被半路打断——本脚本就是用来把这些问题
在测试环境里先炸出来的。

用法：
    python3 -m src.rotate_check --gateway http://127.0.0.1:19000 \\
        --token <access_token> --requests 40

输出一行以 ``failures=<N>`` 结尾可被 grep 的摘要，verify.sh 依赖其中
必须出现 ``failures=0`` 字样。退出码：全部成功为 0，否则为 1。
"""
import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request

ORDER_ID = "A-7781"


def _hit(gateway: str, token: str, results: list, idx: int):
    req = urllib.request.Request(
        f"{gateway}/api/orders/{ORDER_ID}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read()
            ok = resp.status == 200 and b"A-7781" in body
            results[idx] = (ok, resp.status, None)
    except urllib.error.HTTPError as e:
        results[idx] = (False, e.code, e.reason)
    except Exception as e:  # noqa: BLE001 — 探针要把任何异常都算作失败，不能吞掉
        results[idx] = (False, None, repr(e))


def _rotate(gateway: str) -> dict:
    req = urllib.request.Request(f"{gateway}/admin/rotate", data=b"{}", method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="网关证书轮换零失败探针")
    ap.add_argument("--gateway", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--requests", type=int, default=40)
    ap.add_argument("--concurrency", type=int, default=6,
                     help="同时在飞行的请求数，制造真实的重叠窗口场景")
    a = ap.parse_args(argv)

    # 探针本身必须"打不死"：不管压测逻辑内部出什么幺蛾子（线程起不来、
    # 系统资源紧张……），都要落一行可 grep 的 failures=<N> 摘要，而不是
    # 让 verify.sh 拿到一片空输出去猜"到底是没跑起来还是真的挂了"。
    try:
        return _run(a)
    except Exception as e:  # noqa: BLE001
        print(f"rotate_check: requests={a.requests} failures={a.requests} elapsed_ms=0 "
              f"statuses={{}} rotated_to=None rotate_error=None crash={e!r}")
        return 1


def _run(a) -> int:
    n = max(1, a.requests)
    results: list = [None] * n
    sem = threading.Semaphore(a.concurrency)
    rotate_result = {}
    rotate_error = None
    # 轮换故意选在"已经有几个请求在飞、但整批远未打完"的时间点触发，
    # 这样既有用旧证书已经建立/正在建立连接的请求，也有轮换之后才
    # 发出的新请求——覆盖两侧的重叠窗口。
    rotate_after = max(1, n // 4)

    def worker(i: int):
        with sem:
            _hit(a.gateway, a.token, results, i)

    threads = []
    t0 = time.monotonic()
    for i in range(n):
        th = threading.Thread(target=worker, args=(i,), daemon=True)
        th.start()
        threads.append(th)
        if i == rotate_after:
            try:
                rotate_result = _rotate(a.gateway)
            except Exception as e:  # noqa: BLE001
                rotate_error = repr(e)

    for th in threads:
        th.join(timeout=15)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    failures = sum(1 for r in results if r is None or not r[0])
    statuses: dict = {}
    for r in results:
        code = r[1] if r else "no_response"
        statuses[str(code)] = statuses.get(str(code), 0) + 1

    summary = (
        f"rotate_check: requests={n} failures={failures} elapsed_ms={elapsed_ms} "
        f"statuses={statuses} rotated_to={rotate_result.get('rotated_to')} "
        f"rotate_error={rotate_error}"
    )
    print(summary)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
