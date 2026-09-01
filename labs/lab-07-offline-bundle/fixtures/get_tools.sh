#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# 下载本 Lab 需要的三个工具到 tools/（已 gitignore）。
# 这一步需要联网——它属于「构建侧」，客户现场那侧不需要下载任何东西。
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p tools

curl -sSL -o tools/cosign https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64
chmod +x tools/cosign

curl -sSL https://get.helm.sh/helm-v3.16.3-linux-amd64.tar.gz | tar -xz -C /tmp linux-amd64/helm
mv /tmp/linux-amd64/helm tools/helm && chmod +x tools/helm

SYFT=$(curl -sL https://api.github.com/repos/anchore/syft/releases/latest \
  | python3 -c "import sys,json;print(next(a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('linux_amd64.tar.gz')))")
curl -sSL "$SYFT" | tar -xz -C tools syft && chmod +x tools/syft

echo "已下载到 tools/："
for t in cosign helm syft; do printf "  %-8s " "$t"; tools/$t version 2>&1 | grep -oE 'v?[0-9]+\.[0-9]+\.[0-9]+' | head -1; done
