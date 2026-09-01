#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-07 · 构建侧：打一个自包含离线部署包
#
#   bash src/build_bundle.sh --out results/bundle
#
# 这一侧允许联网（要 docker build 拉基础镜像层、要下工具）。真正的约束在
# 另一侧：install_offline.sh 全程断网。所以这里的每一个决定，判据都是
# 「客户现场没网的时候，少了它会不会卡住」。
#
# 产出八样（README 表格）：
#   image.tar image.bundle cosign.pub trusted-root.json
#   sbom-spdx.json sbom-cyclonedx.json chart.tgz manifest.txt
#
# 私钥 cosign.key 只在构建侧临时目录里存在，绝不进包。
set -euo pipefail

LAB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$LAB/tools"
IMAGE=fde-offline-demo:1.0.0        # 与 fixtures/chart/values.yaml 对应

OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --out) OUT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "未知参数：$1" >&2; exit 2 ;;
    esac
done
[ -n "$OUT" ] || { echo "用法：$0 --out <目录>" >&2; exit 2; }

for t in cosign helm syft; do
    [ -x "$T/$t" ] || { echo "缺少 $T/$t，先跑 bash fixtures/get_tools.sh" >&2; exit 3; }
done
command -v docker >/dev/null || { echo "缺少 docker" >&2; exit 3; }

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

# 私钥留在包外的临时目录，退出即删。这一行就是「私钥不进包」的全部实现，
# 但它值得单独写出来——顺手把 cosign.key 拷进 $OUT 是最常见的一次性事故。
KEYDIR="$(mktemp -d)"
trap 'rm -rf "$KEYDIR"' EXIT

step() { printf '[build] %s\n' "$1" >&2; }

# ── 1. 构建镜像并导出 ────────────────────────────────────────────
step "docker build $IMAGE"
docker build -q -t "$IMAGE" "$LAB/fixtures/app" >/dev/null

step "docker save -> image.tar"
docker save "$IMAGE" -o "$OUT/image.tar"

IMAGE_ID=$(docker image inspect "$IMAGE" --format '{{.Id}}')

# ── 2. SBOM（两种格式）────────────────────────────────────────────
# 直接扫 tar，扫的就是要交付的那个文件本身，而不是本地 daemon 里某个
# 同名镜像——这两者在多次构建之后未必是同一个东西。
step "syft scan docker-archive:image.tar -> SPDX + CycloneDX"
SYFT_CHECK_FOR_APP_UPDATE=false "$T/syft" scan "docker-archive:$OUT/image.tar" \
    -q -o "spdx-json=$OUT/sbom-spdx.json" \
    -o "cyclonedx-json=$OUT/sbom-cyclonedx.json"

# ── 3. 签名 + 本地信任根 ──────────────────────────────────────────
# 这三条是本 Lab 的核心。cosign v3.1.3 上 --tlog-upload=false 已弃用会直接报错；
# trusted-root.json 只有几十字节，但少了它客户现场验签会去 tuf-repo-cdn.sigstore.dev
# 拉信任根，断网直接失败——失败发生在「签名对不对」还没开始算之前。
step "cosign generate-key-pair（私钥留在 $KEYDIR，不进包）"
( cd "$KEYDIR" && COSIGN_PASSWORD="" "$T/cosign" generate-key-pair >/dev/null )

step "cosign sign-blob -> image.bundle"
COSIGN_PASSWORD="" "$T/cosign" sign-blob \
    --key "$KEYDIR/cosign.key" --yes --new-bundle-format \
    --bundle "$OUT/image.bundle" "$OUT/image.tar" >/dev/null

step "cosign trusted-root create -> trusted-root.json"
"$T/cosign" trusted-root create --out "$OUT/trusted-root.json" >/dev/null

cp "$KEYDIR/cosign.pub" "$OUT/cosign.pub"      # 只拷公钥

# ── 4. Helm Chart ────────────────────────────────────────────────
step "helm package fixtures/chart -> chart.tgz"
PKGDIR="$(mktemp -d)"
"$T/helm" package "$LAB/fixtures/chart" -d "$PKGDIR" >/dev/null
mv "$PKGDIR"/*.tgz "$OUT/chart.tgz"
rm -rf "$PKGDIR"

# ── 5. 清单 ──────────────────────────────────────────────────────
# 出问题时唯一能说清「到底交付了什么」的东西。校验和用 sha256，
# 版本信息要带上签名/扫描工具的版本——同一份包换个 cosign 大版本
# 就可能验不动（本 Lab 的 v1/v2 bundle 格式就是活例子）。
step "生成 manifest.txt"
ver() { "$T/$1" version 2>&1 | grep -oE 'v?[0-9]+\.[0-9]+\.[0-9]+' | head -1; }
{
    echo "# Lab-07 离线部署包清单"
    echo "bundle_format:   1"
    echo "built_at:        $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "built_on:        $(uname -srm)"
    echo "image_ref:       $IMAGE"
    echo "image_id:        $IMAGE_ID"
    echo
    echo "## 构建侧工具版本（验签工具大版本不一致可能导致包验不动）"
    echo "cosign:          $(ver cosign)"
    echo "helm:            $(ver helm)"
    echo "syft:            $(ver syft)"
    echo "docker:          $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo unknown)"
    echo
    echo "## 产物校验和（sha256）"
    ( cd "$OUT" && sha256sum image.tar image.bundle cosign.pub trusted-root.json \
        sbom-spdx.json sbom-cyclonedx.json chart.tgz )
    echo
    echo "## 验签方式（客户现场，完全断网）"
    echo "cosign verify-blob --key cosign.pub --bundle image.bundle --new-bundle-format \\"
    echo "  --trusted-root trusted-root.json --insecure-ignore-tlog image.tar"
    echo "注：--insecure-ignore-tlog 跳过透明日志核对，是断网换来的取舍，需向安全团队说明。"
    echo
    echo "## 本包不含私钥"
    echo "cosign.key 仅存在于构建侧临时目录，随构建结束销毁。"
} > "$OUT/manifest.txt"

SIZE=$(du -sm "$OUT" | cut -f1)
echo "bundle=$OUT size=${SIZE}MB"
