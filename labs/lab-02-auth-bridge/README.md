# Lab-02 · mTLS + OAuth2 认证桥接网关

服务《前线部署工程师（FDE）：把 AI 交付到真实世界》下册第 6 章 §6.1（超时预算分配）与 §4.3（网关终结模式）。

## 目标

企业现场经常出现这样的组合：**外部/新系统只会说 OAuth2**（Bearer token），
**遗留系统只认 mTLS 客户端证书**（不认、也永远不会去改造成认 OAuth2）。
两边谁也说服不了谁去迁就对方，唯一现实的做法是在中间放一个网关，把协议
转换这件事**在网关这一层彻底终结**——遗留系统完全不需要知道外部客户
用的是 OAuth2、Basic 还是别的什么。

这个 Lab 让你亲手实现这样一个网关，并验证三件容易在现场翻车的事：

1. 对外的 OAuth2 校验是不是真的挡住了无凭据/伪造凭据（401，不是 403，
   更不是什么都不做直接 200）。
2. 对内调遗留系统时有没有**显式的超时预算**——遗留系统一慢，网关是不是
   会陪着一起慢，把 3 秒原样传导给调用方。
3. 遗留系统要求的客户端证书快过期、需要换的时候，网关能不能在**不停机、
   不丢一个请求**的前提下切换过去。

## 架构一览

```
                 Bearer token                    mTLS client cert
调用方  ───────────────────────▶  网关  ───────────────────────▶  遗留系统
                                   │
                                   │ POST /oauth2/introspect
                                   ▼
                                  IdP
```

- **对外**：`src/gateway.py` 是一个标准 OAuth2 资源服务器。`GET /api/orders/{id}`
  要求 `Authorization: Bearer <token>`；网关拿这个 token 去 IdP 的
  `/oauth2/introspect` 换取 `active` / `scope` / `exp`，自己不解析、不签发、
  也不缓存 token 的业务含义，只信任 IdP 的判断（`fixtures/mock_idp.py`）。
- **对内**：网关用 `fixtures/certs/gateway-client.{crt,key}` 做 mTLS 客户端，
  访问只认证书 CN、完全不认 Bearer token 的遗留系统
  （`fixtures/mock_legacy.py`）。调用方（IdP、Bearer token、scope……）这些
  概念在这一跳彻底消失。

## 可替换项（换实现要改哪里）

| 想换什么 | 改哪里 | 注意什么 |
|---|---|---|
| 换 IdP 实现（真实 Keycloak/Okta/Auth0） | `GatewayServer.__init__` 里的 `--idp` 基址 + `Handler._introspect` 里的请求形状 | 真实 IdP 的 introspect 端点可能要求 client 认证（Basic auth 或额外的 client_id/client_secret），mock 版本没做这层，接真实 IdP 时要补上 |
| 换网关框架（FastAPI/Flask/Go） | 只保留 `ClientCertState` / `CertManager` 这两个类描述的"引用计数 + 原子指针替换"模型，路由和 HTTP 处理可以整体换掉 | 换框架后要自己确认新框架的连接池/keep-alive 机制会不会让旧证书的连接"复活"（本实现刻意每次请求新建连接来规避这个问题，见下文轮换一节） |
| 换遗留系统的认证方式（比如从 mTLS 换成 API Key） | `Handler._handle_order` 里"对内"那一段 + 去掉 `CertManager`/`ssl.SSLContext` 相关代码 | 网关终结模式的核心不是"必须用 mTLS"，而是"外部协议不能传导到遗留系统"，具体传导给遗留系统的凭据形式可以是任何东西 |
| 换超时预算的数值 | `src/gateway.py` 顶部的 `IDP_TIMEOUT` / `LEGACY_TIMEOUT` 两个常量 | 改之前先想清楚外部总预算是多少（本 Lab 是 verify.sh 定的 2.5s），再往下分配给每一跳，不要拍脑袋改一跳而不管总预算 |

## 前置条件

- Python 3.12（标准库即可：`http.server` + `ssl` + `urllib`，没有引入第三方依赖）
- 证书已生成：`fixtures/certs/` 下应有 9 个文件（`ca.*`、`legacy-server.*`、
  `gateway-client.*`、`gateway-client-next.*`、`rogue-*`）。如果没有，先跑：

  ```bash
  bash fixtures/gen_certs.sh
  ```

  注意 `gateway-client.crt` 故意只签了 **3 天**——这是特意设计的，逼你在这个
  Lab 里真的面对"证书要轮换"这件事，而不是假装它不存在。

## 步骤

```bash
cd labs/lab-02-auth-bridge

# 一次性把全部 7 项检查跑完（推荐，和讲师验收方式一致）
bash verify.sh
echo $?   # 必须是 0
```

如果想手动分步跑，感受一下网关到底在做什么：

```bash
# 1. 起 mock 服务
python3 fixtures/mock_legacy.py --port 19443 &
python3 fixtures/mock_idp.py    --port 19080 &

# 2. 起网关
python3 -m src.gateway --port 19000 \
    --legacy https://127.0.0.1:19443 --idp http://127.0.0.1:19080 &

# 3. 拿一个 token（client_credentials 流）
TOK=$(curl -s -X POST http://127.0.0.1:19080/oauth2/token \
      -d 'grant_type=client_credentials&client_id=fde-gateway&client_secret=s3cr3t-gateway&scope=orders.read' \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 4. 用这个 token 打网关——注意全程没有出现任何证书
curl -H "Authorization: Bearer $TOK" http://127.0.0.1:19000/api/orders/A-7781

# 5. 没有 token / token 伪造，应该都是 401
curl -i http://127.0.0.1:19000/api/orders/A-7781
curl -i -H "Authorization: Bearer not-a-real-token" http://127.0.0.1:19000/api/orders/A-7781

# 6. 触发超时预算：A-9001 在遗留系统侧固定慢 3 秒
time curl -o /dev/null -s -w '%{http_code}\n' \
     -H "Authorization: Bearer $TOK" http://127.0.0.1:19000/api/orders/A-9001

# 7. 手动触发一次证书轮换（网关内部管理接口，不对外网开放）
curl -X POST http://127.0.0.1:19000/admin/rotate
curl http://127.0.0.1:19000/admin/status   # 看看当前用的是哪一代证书
```

## 证书轮换：重叠窗口是怎么设计的

**现场教训先说在前面**：证书快到期了才临时去申请新证书、走审批、部署、
切换——这条链路本身就要好几天，而"发现快过期"往往就在到期前一两天，
根本来不及。正确的做法是反过来：**新证书提前很久就签好、提前部署到
所有需要它的地方**，在一段**重叠期**内新旧两张证书都对同一个 CA 有效、
都被下游（这里是遗留系统）信任，网关可以在这段窗口内的任意时刻原子切换，
确认切换成功、旧证书不再被使用之后，才去吊销/归档旧证书。

本 Lab 里 `fixtures/gen_certs.sh` 已经把这个模型摆在你面前：
`gateway-client.crt`（3 天有效，"当前在用"）和
`gateway-client-next.crt`（3650 天有效，"下一代"，同一个 CA 签发）**从一开始
就同时存在、同时有效**。轮换这件事，不是"等旧的过期了再着急忙慌去生成
新的"，而是"新的早就在那儿了，随时可以切"。

### 网关侧怎么保证零中断

`src/gateway.py` 里 `CertManager` / `ClientCertState` 两个类是核心：

1. **每一代证书是一个独立的状态对象**（`ClientCertState`），持有自己的
   `ssl.SSLContext` 和一个"当前有多少请求正在用它"的引用计数
   （`acquire()`/`release()`）。
2. **`CertManager.get()` 只做一件事：读一个指针**（`self._current`）。
   Python 里对象引用的读写在 GIL 下是原子的，所以不需要额外加锁就能保证
   "拿到的要么是完整的旧状态，要么是完整的新状态，不会拿到一半"。
3. **轮换（`CertManager.rotate()`）分两步**：先把新证书完整加载进一个
   全新的 `SSLContext`（这一步失败就直接抛异常，`self._current` 纹丝不动，
   不会把网关切到一个加载失败的半成品状态上）；再把 `self._current` 指针
   原子替换成新对象。
4. **旧对象不会被立刻销毁**：切换之前已经在处理中的请求，在自己的调用
   帧里已经通过 `state = self.server.certs.get()` 拿到了*旧*对象的引用，
   `rotate()` 换指针跟它们没有任何关系——它们会用旧证书把自己那次到遗留
   系统的调用走完、`close()` 连接、`release()` 计数，全程无感知。切换
   之后才发起的新请求，`get()` 拿到的自然就是新对象。

### 连接池 / 飞行请求怎么处理

这是"现场最容易出事的一步"里最容易被忽略的细节：如果网关对遗留系统用的
是长连接/连接池（比如 `requests.Session` 配 `HTTPAdapter` 复用连接），
轮换那一刻连接池里**已经用旧证书握手成功的连接**不会自动感知到"证书已经
换了"——它们会带着旧身份继续被复用很久，直到连接超时或被回收，这段时间
里你以为已经切换完成，实际上还有流量在用旧证书。

本实现刻意**不做连接复用**：`Handler._handle_order` 里每次请求都用
`http.client.HTTPSConnection(..., context=state.ssl_context)` 新建一条到
遗留系统的连接，用完立刻 `close()`。这样"一条连接绑定哪一代证书"这件事
在连接创建的瞬间就已经确定并且只存在这一次请求的生命周期里，天然不存在
"池子里挂着旧证书连接"的问题。代价是牺牲了长连接复用带来的性能（每次
握手都要重新做一次 TLS handshake），但对认证桥接网关这种"内部调用量不算
特别夸张、正确性远比这点握手开销重要"的场景，这个取舍是合理的。如果要
换成连接池实现，**必须**在轮换时主动清空/失效持有旧证书的那部分连接，
不能指望它们自然过期。

### `rotate_check.py` 是怎么验证"零失败"的

`src/rotate_check.py` 用 `--concurrency 6` 起一批线程持续对
`GET /api/orders/A-7781` 发请求（默认 40 次），在第 `n // 4` 个请求发出后
的间隙，**用同一个进程的主线程**调用一次 `POST /admin/rotate`——这样保证
轮换确实发生在"一部分请求已经在飞、另一部分还没发出"的重叠窗口中间，而不
是简单地"轮换完了才开始压测"或"压测完了才轮换"（那样测不出任何东西）。
每个请求的结果（状态码、是否包含预期订单号）都会被记录，最后统计
`failures = 状态非 200 或响应体不含订单号的请求数`，全部通过才打印
`failures=0` 并以退出码 0 结束。

## 超时预算实际设了多少

`verify.sh` 定的外部总预算是 **2500ms**（调用方最多能忍到这个数，网关必须
在这之前用 504/502/503 中的一个给出明确答复，不能让下游的 3 秒原样穿过来，
也不能干脆不响应）。网关内部把这份预算切成两跳：

- `IDP_TIMEOUT = 1.0s`：IdP 是本机 mock，正常情况下几毫秒内就回，这个数字
  本身是给"IdP 真的挂了"这种异常情况兜底用的，不指望它会被用满。
- `LEGACY_TIMEOUT = 1.5s`：遗留系统这一跳才是真正会失控的地方
  （`A-9001` 固定慢 3 秒），把大头预算留给它。`http.client.HTTPSConnection`
  的 `timeout` 参数同时约束了 connect 和后续 recv 的 socket 超时，一超时就
  抛 `socket.timeout`，网关捕获后立刻返回 `504`。

两者相加（最坏情况 2.5s）看似正好卡在预算线上，但实际请求里 IdP 那一跳
几乎不会真的用满 1 秒（本机 mock 通常个位数毫秒），所以真实观测到的端到端
延迟（`verify.sh` 里 `MS` 那一栏）稳定在 **1500ms 左右**，比 2500ms 的硬
上限留了近 1 秒的安全余量，足够吸收网络抖动、TLS 握手、Python 解释器
调度这些不确定因素。

## 常见故障排查

- **`[1/7]` 失败，提示缺文件**：先跑 `bash fixtures/gen_certs.sh` 生成证书。
  这一步不属于 `src/` 的职责，Lab 设计上就是把证书生成和网关实现分开。
- **`[4/7]` 端到端穿透失败，`results/gateway.log` 里有 `ModuleNotFoundError`**：
  确认是在 `lab-02-auth-bridge/` 目录下用 `python3 -m src.gateway` 启动的
  （`-m` 形式依赖当前工作目录能找到 `src` 包），而不是直接
  `python3 src/gateway.py`。
- **`[5/7]` 无 token 返回的是 000/超时而不是 401**：说明网关根本没启动成功，
  去看 `results/gateway.log`，通常是端口被占用或者证书路径不对
  （`--cert-dir` 默认指向 `fixtures/certs`，用相对路径启动网关时注意
  当前工作目录）。
- **`[6/7]` 超时预算失败，状态码是 `000`**：这表示网关没有响应（进程没起来
  或已经崩了），不是"超时预算生效"，去看 `results/gateway.log` 里的
  traceback；如果状态码是 `200` 且耗时 ~3000ms，说明超时没生效，检查
  `LEGACY_TIMEOUT` 是否真的传给了 `HTTPSConnection`。
- **`[7/7]` 轮换测试偶发失败（个别请求超时/连接被拒）**：先检查是不是在
  `Handler._handle_order` 里用了连接池/长连接复用——按上面"连接池"一节
  的解释，复用连接会让轮换出现"旧连接還在用旧证书"的窗口。也检查
  `CertManager.rotate()` 是否在真正切换指针*之前*就已经让旧
  `SSLContext` 失效——正确顺序应该是"新证书加载成功 → 原子替换指针"，
  不能反过来。
- **想确认到底轮换有没有真的生效**：`curl http://127.0.0.1:19000/admin/status`
  会返回当前生效的证书代号（`current`）和上一代的飞行请求残量
  （`previous.inflight`），排障时很有用。

## 延伸练习

1. **回滚**：给 `CertManager.rotate()` 加一个"切回 `current`"的路径（把
   `NAMED` 从两个固定名字换成一个可以来回切换的小状态机），并验证回滚
   同样能做到零失败。
2. **强制吊销**：现在的实现里旧证书对象只是"不再被新请求使用"，永远不会
   真正被"吊销"。给 `ClientCertState` 加一个 `retire(timeout)` 方法，
   轮询/等待 `inflight` 归零（带超时），归零后打日志"安全退役"，超时未
   归零则告警——这才是现场真正会做的"确认无流量后再吊销"。
3. **给 introspect 加缓存**：`mock_idp.py` 的 token TTL 只有 120 秒，真实
   环境里 introspect 往往是一次网络调用，QPS 高了会成为瓶颈。给
   `Handler._introspect` 加一个"按 token 缓存到较短 TTL（比如 5 秒或
   `min(5, exp-now)`）"的内存缓存，并想清楚：缓存命中期间如果 IdP 那边
   把 token 主动吊销了，网关要多久才能感知到——这是"缓存换性能"必须要
   回答的问题。
4. **换成真正的双向健康检查**：现在网关对遗留系统的"健康"没有任何主动
   探测，只有请求失败了才知道。加一个后台线程定期（比如每 5 秒）用当前
   证书状态对遗留系统做一次轻量探测（比如 `_stats` 端点），探测失败时
   在 `/admin/status` 里体现出来，为运维提供比"等用户报错"更早的信号。
