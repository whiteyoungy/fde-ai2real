#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# 生成 Lab-03 所需的证书体系（比 Lab-02 简化，只保留桥接必需的三张）。
#
#   ca             自签根 CA
#   erp-server     遗留 ERP 的服务端证书（要求 mTLS）
#   bridge-client  MCP Server 访问 ERP 用的客户端证书
#
# 这套证书是「鉴权桥接」的下半层：模型侧完全看不到它们的存在。
set -euo pipefail
cd "$(dirname "$0")"
OUT="certs"; rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"

subj() { echo "/C=CN/O=FDE-Lab/CN=$1"; }
q() { openssl "$@" >/dev/null 2>&1; }

q req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout ca.key -out ca.crt -subj "$(subj "FDE-Lab Root CA")"

# 服务端证书必须带 SAN，否则 Python ssl 校验主机名会失败
cat > san.cnf <<'EOF'
subjectAltName = DNS:erp.internal, DNS:localhost, IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF
q req -newkey rsa:2048 -nodes -keyout erp-server.key \
  -out erp-server.csr -subj "$(subj erp.internal)"
q x509 -req -in erp-server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out erp-server.crt -days 3650 -extfile san.cnf

cat > client.cnf <<'EOF'
extendedKeyUsage = clientAuth
EOF
q req -newkey rsa:2048 -nodes -keyout bridge-client.key \
  -out bridge-client.csr -subj "$(subj mcp-bridge-01)"
q x509 -req -in bridge-client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out bridge-client.crt -days 3650 -extfile client.cnf

rm -f ./*.csr ./*.cnf ./*.srl
chmod 600 ./*.key

echo "证书已生成到 fixtures/certs/："
for f in ca.crt erp-server.crt bridge-client.crt; do
    cn=$(openssl x509 -in "$f" -noout -subject | sed 's/.*CN *= *//')
    printf "  %-20s CN=%s\n" "$f" "$cn"
done
