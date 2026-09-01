#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
# Lab-02 mTLS + OAuth2 认证桥接 · 验收脚本
#
# 7 项检查，全部 OK 且 exit 0 才算通过。
# 测退出码不要放进管道：bash verify.sh > /tmp/v.log 2>&1; echo $?
set -uo pipefail
cd "$(dirname "$0")"

C=fixtures/certs
# 用 19xxx 段，避开常见服务占用（实测 9000 上有别的服务，会污染结果）
LEGACY_PORT=19443; IDP_PORT=19080; GW_PORT=19000
PASS=0; FAIL=0
ok()  { printf '[%s/7] %-24s OK (%s)\n'   "$1" "$2" "$3"; PASS=$((PASS+1)); }
bad() { printf '[%s/7] %-24s FAIL (%s)\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

cleanup() { pkill -f 'fixtures/mock_legacy.py' 2>/dev/null; pkill -f 'fixtures/mock_idp.py' 2>/dev/null;
            pkill -f 'src.gateway' 2>/dev/null; sleep 0.3; }
trap cleanup EXIT
cleanup

echo "== Lab-02 mTLS + OAuth2 认证桥接 验收 =="
echo

mkdir -p results

# ── [1/7] 证书体系完整 ─────────────────────────────────────────
MISS=""
for f in ca.crt legacy-server.crt legacy-server.key gateway-client.crt gateway-client.key \
         gateway-client-next.crt gateway-client-next.key rogue-client.crt rogue-client.key; do
    [ -f "$C/$f" ] || MISS="$MISS $f"
done
if [ -z "$MISS" ]; then
    EXP=$(openssl x509 -in "$C/gateway-client.crt" -noout -enddate | cut -d= -f2)
    ok 1 "证书体系完整" "9 个文件齐；当前网关证书到期 $EXP"
else
    bad 1 "证书体系完整" "缺:$MISS；先跑 bash fixtures/gen_certs.sh"
fi

# ── [2/7] mock 服务可启动 ──────────────────────────────────────
python3 fixtures/mock_legacy.py --port $LEGACY_PORT > results/legacy.log 2>&1 &
python3 fixtures/mock_idp.py    --port $IDP_PORT    > results/idp.log    2>&1 &
sleep 2.5
L_UP=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 --cacert $C/ca.crt \
        --cert $C/gateway-client.crt --key $C/gateway-client.key \
        https://127.0.0.1:$LEGACY_PORT/legacy/v1/_stats || echo 000)
I_UP=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:$IDP_PORT/_stats || echo 000)
if [ "$L_UP" = "200" ] && [ "$I_UP" = "200" ]; then
    ok 2 "mock 服务可启动" "legacy(mTLS):$LEGACY_PORT  idp:$IDP_PORT"
else
    bad 2 "mock 服务可启动" "legacy=$L_UP idp=$I_UP，见 results/*.log"
fi

# ── [3/7] 遗留系统拒绝无效客户端证书 ───────────────────────────
# 这是本 Lab 的地基：如果 mock 不拒，后面测的都是假的。
NOCERT=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 --cacert $C/ca.crt \
          https://127.0.0.1:$LEGACY_PORT/legacy/v1/orders/A-7781 2>/dev/null || echo REJECTED)
ROGUE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 --cacert $C/ca.crt \
          --cert $C/rogue-client.crt --key $C/rogue-client.key \
          https://127.0.0.1:$LEGACY_PORT/legacy/v1/orders/A-7781 2>/dev/null || echo REJECTED)
if [ "$NOCERT" != "200" ] && [ "$ROGUE" != "200" ]; then
    ok 3 "无效证书被拒" "无证书=$NOCERT 野CA证书=$ROGUE，均在握手阶段拒绝"
else
    bad 3 "无效证书被拒" "无证书=$NOCERT 野CA=$ROGUE，出现 200 说明 mTLS 未真正生效"
fi

# ── [4/7] 网关端到端穿透 ───────────────────────────────────────
# 对外 OAuth2 资源服务器，对内 mTLS 调遗留系统。客户端全程不接触任何证书。
python3 -m src.gateway --port $GW_PORT --legacy https://127.0.0.1:$LEGACY_PORT \
        --idp http://127.0.0.1:$IDP_PORT > results/gateway.log 2>&1 &
sleep 2.5
TOK=$(curl -s --max-time 5 -X POST http://127.0.0.1:$IDP_PORT/oauth2/token \
      -d 'grant_type=client_credentials&client_id=fde-gateway&client_secret=s3cr3t-gateway&scope=orders.read' \
      | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
E2E=$(curl -s --max-time 10 -H "Authorization: Bearer $TOK" \
      http://127.0.0.1:$GW_PORT/api/orders/A-7781 2>/dev/null)
if echo "$E2E" | grep -q 'A-7781' && echo "$E2E" | grep -q 'SHIPPED\|shipped'; then
    ok 4 "端到端穿透" "客户端仅用 Bearer token，网关内部走 mTLS 取到订单"
else
    bad 4 "端到端穿透" "返回:$(echo "$E2E" | head -c 80)"
fi

# ── [5/7] 网关拒绝无效/越权凭据 ────────────────────────────────
NOAUTH=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
         http://127.0.0.1:$GW_PORT/api/orders/A-7781 2>/dev/null || echo 000)
BADTOK=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
         -H "Authorization: Bearer not-a-real-token" \
         http://127.0.0.1:$GW_PORT/api/orders/A-7781 2>/dev/null || echo 000)
if [ "$NOAUTH" = "401" ] && [ "$BADTOK" = "401" ]; then
    ok 5 "无效凭据被拒" "无 token=$NOAUTH 伪造 token=$BADTOK"
else
    bad 5 "无效凭据被拒" "无 token=$NOAUTH 伪造 token=$BADTOK，均应为 401"
fi

# ── [6/7] 超时预算：慢接口不拖垮网关 ───────────────────────────
# A-9001 在遗留系统侧固定慢 3 秒。网关必须有超时预算并快速失败，
# 而不是把 3 秒原样传导给调用方。
T0=$(date +%s%N)
SLOW=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
       -H "Authorization: Bearer $TOK" http://127.0.0.1:$GW_PORT/api/orders/A-9001 2>/dev/null || echo 000)
T1=$(date +%s%N); MS=$(( (T1 - T0) / 1000000 ))
# 必须是网关自己给出的网关错误码（504/502/503），不能是连接被拒（000）——
# 否则"网关没起来"会被误判成"超时预算生效"。
case "$SLOW" in
  504|502|503) GW_ERR=1 ;;
  *)           GW_ERR=0 ;;
esac
if [ "$MS" -lt 2500 ] && [ "$GW_ERR" -eq 1 ]; then
    ok 6 "超时预算生效" "${MS}ms 内以 $SLOW 快速失败（遗留侧固定慢 3000ms）"
else
    bad 6 "超时预算生效" "耗时 ${MS}ms 状态 $SLOW；应在 2500ms 内返回 504/502/503。\
状态 000 表示网关未响应，不算通过"
fi

# ── [7/7] 证书轮换：切换期间零失败 ─────────────────────────────
# 现场最容易出事的一步。网关要支持在不中断请求的前提下换掉客户端证书。
ROT=$(python3 -m src.rotate_check --gateway http://127.0.0.1:$GW_PORT \
      --token "$TOK" --requests 40 2>/dev/null)
if [ -n "$ROT" ] && echo "$ROT" | grep -q 'failures=0'; then
    ok 7 "证书轮换零失败" "$ROT"
else
    bad 7 "证书轮换零失败" "${ROT:-无输出}，要求轮换全程 failures=0"
fi

echo
echo "== 汇总：$PASS 项通过 / $FAIL 项失败 =="
# 只判 FAIL=0 不够：某项检查若因脚本自身出错而静默跳过，FAIL 不会增加，
# 会把「少跑了一项」误报成「全部通过」。必须同时确认通过项数达到 7。
if [ $FAIL -eq 0 ] && [ $PASS -eq 7 ]; then echo "验收通过。"; exit 0
else echo "验收未通过：通过 $PASS/7，失败 $FAIL。少于 7 项说明有检查未执行完。"; exit 1; fi
