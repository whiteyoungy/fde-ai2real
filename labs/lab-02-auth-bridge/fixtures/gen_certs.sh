#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# 生成 Lab-02 所需的证书体系。
#
#   ca                    自签根 CA
#   legacy-server         遗留系统的服务端证书（要求 mTLS）
#   gateway-client        网关的客户端证书（当前有效）
#   gateway-client-next   网关的下一代客户端证书（轮换用，同一 CA 签发）
#   rogue-client          另一个 CA 签发的客户端证书（负例：应被拒绝）
#
# 有效期故意设短（gateway-client 3 天），让「凭据轮换」不是纸上谈兵。
set -euo pipefail
cd "$(dirname "$0")"
OUT="certs"; rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"

subj() { echo "/C=CN/O=FDE-Lab/CN=$1"; }
q() { openssl "$@" >/dev/null 2>&1; }

# ── 根 CA ──────────────────────────────────────────────────────
q req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout ca.key -out ca.crt -subj "$(subj "FDE-Lab Root CA")"

# ── 遗留系统服务端证书（含 SAN，否则 Python ssl 校验主机名会失败）──
q req -newkey rsa:2048 -nodes -keyout legacy-server.key \
  -out legacy-server.csr -subj "$(subj legacy.internal)"
cat > san.cnf <<'EOF'
subjectAltName = DNS:legacy.internal, DNS:localhost, IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF
q x509 -req -in legacy-server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out legacy-server.crt -days 3650 -extfile san.cnf

# ── 网关客户端证书：当前这张故意只签 3 天 ──────────────────────
cat > client.cnf <<'EOF'
extendedKeyUsage = clientAuth
EOF
q req -newkey rsa:2048 -nodes -keyout gateway-client.key \
  -out gateway-client.csr -subj "$(subj gateway-01)"
q x509 -req -in gateway-client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out gateway-client.crt -days 3 -extfile client.cnf

# ── 轮换用的下一张，同 CA 签发，有效期长 ───────────────────────
q req -newkey rsa:2048 -nodes -keyout gateway-client-next.key \
  -out gateway-client-next.csr -subj "$(subj gateway-02)"
q x509 -req -in gateway-client-next.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out gateway-client-next.crt -days 3650 -extfile client.cnf

# ── 负例：另一个 CA 签发，遗留系统必须拒绝 ─────────────────────
q req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout rogue-ca.key -out rogue-ca.crt -subj "$(subj "Rogue CA")"
q req -newkey rsa:2048 -nodes -keyout rogue-client.key \
  -out rogue-client.csr -subj "$(subj attacker)"
q x509 -req -in rogue-client.csr -CA rogue-ca.crt -CAkey rogue-ca.key \
  -CAcreateserial -out rogue-client.crt -days 3650 -extfile client.cnf

rm -f *.csr *.cnf *.srl
chmod 600 ./*.key

echo "证书已生成到 fixtures/certs/："
for f in ca.crt legacy-server.crt gateway-client.crt gateway-client-next.crt rogue-client.crt; do
    exp=$(openssl x509 -in "$f" -noout -enddate | cut -d= -f2)
    cn=$(openssl x509 -in "$f" -noout -subject | sed 's/.*CN *= *//')
    printf "  %-26s CN=%-18s 到期 %s\n" "$f" "$cn" "$exp"
done
