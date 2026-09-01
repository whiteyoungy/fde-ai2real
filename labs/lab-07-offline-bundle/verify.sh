#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-07 自包含离线部署包 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

T="$PWD/tools"
BUNDLE="$PWD/results/bundle"
CNAME=lab07-svc
PASS=0; FAIL=0
ok()  { printf '[%s/7] %-26s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-26s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

cleanup() { docker rm -f "$CNAME" >/dev/null 2>&1; }
trap cleanup EXIT
cleanup

echo "== Lab-07 自包含离线部署包 验收 =="
echo
mkdir -p results
rm -rf "$BUNDLE" results/*.log

# ── [1/7] 工具链就位 ───────────────────────────────────────────
VS=""
for t in cosign helm syft; do
    if [ -x "$T/$t" ]; then
        VS="$VS $t=$("$T/$t" version 2>&1 | grep -oE 'v?[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
    else
        VS="$VS $t=缺失"
    fi
done
if ! echo "$VS" | grep -q 缺失; then
    ok 1 "工具链就位" "${VS# }"
else
    bad 1 "工具链就位" "${VS# }；先跑 bash fixtures/get_tools.sh"
fi

# ── 构建离线包（这一步允许联网，它是「构建侧」） ───────────────
BUILD=$(bash src/build_bundle.sh --out "$BUNDLE" 2>results/build.err)

# ── [2/7] 离线包产出完整 ───────────────────────────────────────
# 八类产物，缺一类客户现场就会卡住（对应 13.2 节的五步 + 信任根 + 清单）
MISS=""
for f in image.tar image.bundle cosign.pub trusted-root.json \
         sbom-spdx.json sbom-cyclonedx.json chart.tgz manifest.txt; do
    [ -f "$BUNDLE/$f" ] || MISS="$MISS $f"
done
SZ=$(du -sm "$BUNDLE" 2>/dev/null | cut -f1)
if [ -z "$MISS" ]; then
    ok 2 "离线包产出完整" "8 类产物齐备，共 ${SZ}MB"
else
    bad 2 "离线包产出完整" "缺:${MISS}。build 输出:${BUILD:-无} $(head -c 100 results/build.err 2>/dev/null)"
fi

# ── [3/7] SBOM 真实可解析 ──────────────────────────────────────
# 空壳 SBOM 也是合法 JSON。要求两种格式都能解析且组件数达到量级。
D3=$(python3 - "$BUNDLE" <<'PY' 2>&1
import json, pathlib, sys
b = pathlib.Path(sys.argv[1])
probs, counts = [], {}
for name, key in (("sbom-spdx.json", "packages"), ("sbom-cyclonedx.json", "components")):
    p = b / name
    if not p.exists():
        probs.append(f"{name} 不存在"); continue
    try:
        d = json.loads(p.read_text())
    except Exception as e:
        probs.append(f"{name} 解析失败：{e}"); continue
    n = len(d.get(key) or [])
    counts[name] = n
    if n < 20:
        probs.append(f"{name} 只有 {n} 个{key}，像是空壳")
print("BAD " + "；".join(probs[:2]) if probs else
      "OK " + "，".join(f"{k} {v} 项" for k, v in counts.items()))
PY
)
if [ "${D3:0:2}" = "OK" ]; then ok 3 "SBOM 真实可解析" "${D3:3}"
else bad 3 "SBOM 真实可解析" "${D3:4}"; fi

# ── [4/7] 断网验签通过 ─────────────────────────────────────────
# unshare -rn 给一个完全没有网络的命名空间。这是本 Lab 的核心断言：
# cosign 默认会去 tuf-repo-cdn.sigstore.dev 拉信任根，断网直接失败，
# 必须随包带一份本地 trusted root 才能验得动。
if [ ! -f "$BUNDLE/image.bundle" ] || [ ! -f "$BUNDLE/trusted-root.json" ]; then
    V4="离线包里没有 image.bundle 或 trusted-root.json，本项无从判断；先看第 2 项"
else
    V4=$(cd "$BUNDLE" && timeout 90 unshare -rn "$T/cosign" verify-blob \
          --key cosign.pub --bundle image.bundle --new-bundle-format \
          --trusted-root trusted-root.json --insecure-ignore-tlog image.tar 2>&1)
fi
if echo "$V4" | grep -q "Verified OK"; then
    ok 4 "断网验签通过" "unshare -rn 无网络命名空间内验签成功"
else
    bad 4 "断网验签通过" "$(echo "$V4" | tail -1 | head -c 160)"
fi

# ── [5/7] 篡改必被拒（负例） ───────────────────────────────────
# 没有这一项，第 4 项证明不了任何事——一个永远返回成功的验签也能过。
# 前置：产物不全时不能报「篡改竟然通过了」——那是把「没构建出来」
# 误诊成「验签形同虚设」，会把人引向完全错误的方向。
if [ ! -f "$BUNDLE/image.tar" ] || [ ! -f "$BUNDLE/image.bundle" ]; then
    V5="__NOBUNDLE__"
else
    cp "$BUNDLE/image.tar" results/tampered.tar
    printf 'x' >> results/tampered.tar
    V5=$(cd "$BUNDLE" && timeout 90 unshare -rn "$T/cosign" verify-blob \
          --key cosign.pub --bundle image.bundle --new-bundle-format \
          --trusted-root trusted-root.json --insecure-ignore-tlog \
          ../tampered.tar 2>&1)
fi
if [ "$V5" = "__NOBUNDLE__" ]; then
    bad 5 "篡改必被拒" "离线包产物不全，本项无从判断；先看第 2 项"
elif echo "$V5" | grep -qi "invalid signature\|failed to verify"; then
    ok 5 "篡改必被拒" "改一个字节即报 invalid signature，验签确实在验"
else
    bad 5 "篡改必被拒" "篡改后竟然通过了：$(echo "$V5" | tail -1 | head -c 120)。验签走过场比不验更危险"
fi

# ── [6/7] 断网安装能起服务 ─────────────────────────────────────
# 安装脚本全程在无网络命名空间里跑；服务容器用 --network none 起，
# 靠 docker exec 从容器内部做健康检查。
INST=$(timeout 240 unshare -rn bash src/install_offline.sh --bundle "$BUNDLE" --name "$CNAME" 2>results/install.err)
sleep 2
HEALTH=$(docker exec "$CNAME" python -c "
import urllib.request,json
print(json.load(urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=5))['ok'])" 2>/dev/null || echo False)
NET=$(docker inspect "$CNAME" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | tr -d ' ')
if [ "$HEALTH" = "True" ] && [ "$NET" = "none" ]; then
    ok 6 "断网安装能起服务" "安装脚本在无网络命名空间内完成；服务容器网络模式 $NET，健康检查通过"
else
    bad 6 "断网安装能起服务" "健康检查=$HEALTH 容器网络=${NET:-未启动}（应为 none）。\
install 输出:${INST:-无} $(head -c 120 results/install.err 2>/dev/null)"
fi

# ── [7/7] 渲染出的 manifest 符合离线约束 ───────────────────────
# 注意：这里必须先落盘再用 argv 传路径，不能写成
#   helm template ... | python3 - <<'PY'
# heredoc 的重定向优先于管道，会把 stdin 顶掉，python 读到的是空串，
# 于是这一项永远报「没渲染出任何内容」——一个永远失败的检查同样是坏检查。
"$T/helm" template lab07 "$BUNDLE/chart.tgz" > results/rendered.yaml 2>results/helm.err
D7=$(python3 - results/rendered.yaml <<'PY' 2>&1
import re, sys
y = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else ""
if not y.strip():
    print("BAD helm template 没有渲染出任何内容"); sys.exit()
probs = []
pull = re.findall(r"imagePullPolicy:\s*(\S+)", y)
if not pull:
    probs.append("渲染结果里没有 imagePullPolicy")
elif any(p != "Never" for p in pull):
    probs.append(f"imagePullPolicy={pull}，断网环境必须是 Never")
if "runAsNonRoot: true" not in y:
    probs.append("没有 runAsNonRoot: true，很多客户安全基线会卡")
if "startupProbe" not in y:
    probs.append("没有 startupProbe，冷启动慢的服务会被 liveness 反复重启")
print("BAD " + "；".join(probs[:2]) if probs else
      f"OK imagePullPolicy={pull[0]}、runAsNonRoot、startupProbe 均已渲染")
PY
)
if [ "${D7:0:2}" = "OK" ]; then ok 7 "manifest 符合离线约束" "${D7:3}"
else bad 7 "manifest 符合离线约束" "${D7:4} $(head -c 80 results/helm.err 2>/dev/null)"; fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
