#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-07 · 客户侧：离线安装
#
#   bash src/install_offline.sh --bundle results/bundle --name lab07-svc
#
# 这个脚本会被放进 `unshare -rn`（一个完全没有网络接口的命名空间）里执行。
# 里面不允许有任何出站请求：不许 curl、不许 docker pull、不许任何隐式拉取。
# docker CLI 走 /var/run/docker.sock 这条 unix socket 不算网络，是允许的。
#
# 顺序是有意义的，不能调换：
#   验签 → 校验 SBOM → docker load → 起服务（--network none）→ 自证健康
# 验签失败必须立刻中止。一个"验完了继续往下装"的脚本，等于没有验签——
# 而它比不验更危险，因为它给了你一种已经验过的错觉。
set -euo pipefail

LAB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE=""; NAME=""
HEALTH_TIMEOUT=60

while [ $# -gt 0 ]; do
    case "$1" in
        --bundle) BUNDLE="${2:-}"; shift 2 ;;
        --name)   NAME="${2:-}";   shift 2 ;;
        -h|--help) sed -n '2,14p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "未知参数：$1" >&2; exit 2 ;;
    esac
done
[ -n "$BUNDLE" ] && [ -n "$NAME" ] || {
    echo "用法：$0 --bundle <目录> --name <容器名>" >&2; exit 2; }
BUNDLE="$(cd "$BUNDLE" && pwd)"

step() { printf '[install] %s\n' "$1" >&2; }
fail() { printf '[install] 中止：%s\n' "$1" >&2; exit 1; }

# 验签工具。真实交付里 cosign 二进制也要随 U 盘带（141MB，本 Lab 为了
# 不把包撑大而放在 tools/），客户现场不可能现下一个。
COSIGN=""
for c in "$BUNDLE/bin/cosign" "$LAB/tools/cosign" "$(command -v cosign 2>/dev/null || true)"; do
    [ -n "$c" ] && [ -x "$c" ] && { COSIGN="$c"; break; }
done
[ -n "$COSIGN" ] || fail "找不到 cosign，无法验签"
command -v docker >/dev/null || fail "找不到 docker"

for f in image.tar image.bundle cosign.pub trusted-root.json \
         sbom-spdx.json sbom-cyclonedx.json chart.tgz manifest.txt; do
    [ -f "$BUNDLE/$f" ] || fail "离线包缺少 $f"
done

# ── 0. 清单校验和 ────────────────────────────────────────────────
# 这一步只挡"传输途中损坏/被换掉的辅助文件"，挡不住有心人（清单本身没签名）。
# 真正的信任锚是下一步的签名。顺序上先做它，是因为它便宜且能给出更清楚的报错。
step "核对 manifest.txt 里的 sha256"
if ! ( cd "$BUNDLE" && grep -E '^[0-9a-f]{64}  ' manifest.txt | sha256sum -c --quiet - ); then
    fail "manifest.txt 校验和不匹配，包在传输中被改动或损坏"
fi

# ── 1. 验签（断网）────────────────────────────────────────────────
# --trusted-root：不带它 cosign 会去 tuf-repo-cdn.sigstore.dev 拉信任根，
#                 断网时在"签名对不对"还没开始算之前就失败。
# --insecure-ignore-tlog：签名时没上传透明日志，验签默认却要求至少一条记录。
#                 这是断网换来的取舍，不是可以随手加的开关。
step "cosign verify-blob（离线，用随包的 trusted-root.json）"
set +e
VOUT=$( cd "$BUNDLE" && "$COSIGN" verify-blob \
            --key cosign.pub --bundle image.bundle --new-bundle-format \
            --trusted-root trusted-root.json --insecure-ignore-tlog \
            image.tar 2>&1 )
VRC=$?
set -e
# 退出码和输出都要看：只看输出会被"命令根本没跑起来"骗过，
# 只看退出码则会漏掉个别工具版本把失败打在 stdout 却返回 0 的情况。
if [ $VRC -ne 0 ] || ! echo "$VOUT" | grep -q "Verified OK"; then
    echo "$VOUT" >&2
    fail "image.tar 验签未通过（rc=$VRC），不再继续安装"
fi
step "验签通过：image.tar 与 image.bundle 匹配"

# ── 2. SBOM 存在且可解析 ─────────────────────────────────────────
# "文件在"不等于"能用"。空壳 SBOM 也是合法 JSON，客户审计那关过不去。
step "校验两份 SBOM 可解析"
python3 - "$BUNDLE" <<'PY' >&2 || fail "SBOM 校验未通过"
import json, pathlib, sys
b = pathlib.Path(sys.argv[1]); bad = []
for name, key in (("sbom-spdx.json", "packages"), ("sbom-cyclonedx.json", "components")):
    try:
        n = len(json.loads((b / name).read_text()).get(key) or [])
    except Exception as e:
        bad.append(f"{name} 解析失败：{e}"); continue
    if n == 0:
        bad.append(f"{name} 是空壳（0 个 {key}）")
    else:
        print(f"[install]   {name}: {n} 个 {key}")
if bad:
    print("[install]   " + "；".join(bad)); sys.exit(1)
PY

# ── 3. 加载镜像 ──────────────────────────────────────────────────
IMAGE=$(grep -E '^image_ref:' "$BUNDLE/manifest.txt" | awk '{print $2}')
[ -n "$IMAGE" ] || fail "manifest.txt 里没有 image_ref"
step "docker load -i image.tar（$IMAGE）"
docker load -i "$BUNDLE/image.tar" >&2

# ── 4. Chart 可用性 ──────────────────────────────────────────────
# 本 Lab 用 Docker 起服务（2 核机器上跑得动），chart 的渲染正确性由
# verify.sh 第 7 项单独验。这里只确认交付的 tgz 不是坏文件。
tar -tzf "$BUNDLE/chart.tgz" >/dev/null 2>&1 || fail "chart.tgz 不是有效的 Helm 包"
step "chart.tgz 可解包"

# ── 5. 起服务 ────────────────────────────────────────────────────
# --network none：容器完全没有网络接口。带网络起来的服务证明不了它在
#                 断网环境能跑。--pull=never 是 docker 侧的 imagePullPolicy: Never。
step "docker run --network none --name $NAME"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --network none --pull=never \
    --restart=no --read-only --tmpfs /tmp \
    -e APP_VERSION=1.0.0 -e PORT=8080 "$IMAGE" >/dev/null

# ── 6. 自证健康 ──────────────────────────────────────────────────
# 容器没有网络接口，从外面根本够不着，健康检查只能从容器内部发起。
# 装完不自查的脚本，等于把"到底起没起来"留给客户去发现。
step "健康检查（docker exec 从容器内部打 /healthz）"
OK=""
for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    if docker exec "$NAME" python -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3))
raise SystemExit(0 if d.get('ok') else 1)" >/dev/null 2>&1; then
        OK=1; break
    fi
    docker inspect "$NAME" --format '{{.State.Running}}' 2>/dev/null | grep -q true \
        || { docker logs "$NAME" >&2 2>&1 || true; fail "容器已退出"; }
    sleep 1
done
[ -n "$OK" ] || { docker logs "$NAME" >&2 2>&1 || true
                  fail "${HEALTH_TIMEOUT}s 内健康检查未通过"; }

NET=$(docker inspect "$NAME" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')
[ "$NET" = "none" ] || fail "容器网络模式是 $NET，应为 none"

echo "service=up name=$NAME image=$IMAGE network=$NET"
