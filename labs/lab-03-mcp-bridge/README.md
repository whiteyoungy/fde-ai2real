# Lab-03 · 遗留 API 封装为 MCP Server

**关联章节**：下册第 5 章（上下文工程与 MCP）、下册第 12 章（案例一 · 用 MCP 盘活遗留大型机）
**预计耗时**：6–8 小时
**前置**：Lab-02 的 mTLS 概念（不必先做完，但读过下册第 6 章会顺很多）

## 这个 Lab 要解决什么

客户有一套只认 mTLS 客户端证书的遗留 ERP。业务方想让 Agent 能查订单、写备注、走审批。

难点不在"调通接口"，而在**边界怎么划**：

- 模型不该知道证书在哪、什么时候过期、怎么轮换。它只该看到"调用成功"或"要不要重试"。
- 遗留系统会抽风。一次超时不能拖垮整个 Agent 会话。
- **审批是不可逆操作。** 模型选错工具的代价不是"重来一次"，是一笔钱批出去了。

第三条是本 Lab 真正的重点。前两条是工程问题，第三条是**工具描述写得好不好**的问题——模型没读过你的代码，它只能靠工具名和 docstring 判断该不该调用。

## 版本锁定（重要）

```
mcp==2.0.0
```

**必须锁死版本号。** `pip install mcp` 不加版本号现在装的是 v2，而绝大多数现存教程是照 v1 写的，直接照抄会报 `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`。

本 Lab 用进程内客户端，不经过外部 MCP host。**如果你的交付要接 Claude Desktop 或 IDE 插件，先实测目标 host 支持到哪个规范版本**——v2 对应的 2026-07-28 规范移除了协议级 session，老 host 可能还没跟上。没有官方兼容矩阵可查，只能自己测。

另外两个实测过的坑（`mcp` 2.0.0）：

| MCP 规范文档写的 | Python SDK 实际是 |
|---|---|
| `result.isError` | `result.is_error` |
| `tool.inputSchema` | `tool.input_schema` |

`inputSchema` 写错会直接 `AttributeError`，报错响亮。危险的是 `getattr(result, "isError", False)`——**字段名写错时它不报错，只会静默返回 `False`**，把工具报错当成调用成功继续往下传。

## 目录结构

```
lab-03-mcp-bridge/
├── README.md
├── requirements.txt
├── verify.sh                    # 验收脚本，8 项全过且退出码 0 才算通过
├── fixtures/
│   ├── gen_certs.sh             # 生成 CA / ERP 服务端 / 桥接客户端证书
│   ├── mock_erp.py              # 只认 mTLS 的遗留 ERP，带故障注入
│   ├── tool_selection.jsonl     # 10 条自然语言 → 期望工具的测试集
│   └── certs/                   # gen_certs.sh 产出（已 gitignore）
├── src/                         # 你要实现的部分
│   ├── bridge.py                # ERP 客户端：mTLS、重试、熔断
│   ├── server.py                # MCP Server：3 个工具
│   ├── check_tools.py           # 各项验收的探针 CLI
│   └── tool_select.py           # 工具选择准确率评测
└── results/                     # 运行产物（已 gitignore）
```

## 三个工具

| 工具 | 对应 ERP 接口 | 性质 |
|---|---|---|
| `get_order_status` | `GET /erp/v2/orders/{id}` | 只读，可重试 |
| `add_order_note` | `POST /erp/v2/orders/{id}/notes` | 写入，可重试（重复写备注代价可控） |
| `approve_order` | `POST /erp/v2/orders/{id}/approve` | **不可逆**，误触发零容忍 |

工具边界要单一职责——不要把"查询+审批"揉进一个工具里，否则模型没法只做前一半。

## 三类失败必须区分开

遗留 ERP 的失败不是一种东西，桥接层要能分清：

| ERP 返回 | 含义 | 该怎么办 |
|---|---|---|
| 503 | 临时不可用 | **重试**，退避 |
| 超时 | 慢或挂了 | 快速失败，返回 `retryable: true` |
| 409 `ORDER_NOT_IN_PENDING_APPROVAL` | 状态不对 | **不要重试**，重试一万次也不会变 |
| 404 `ORDER_NOT_FOUND` | 单号不存在 | **不要重试**，应提示用户核对单号 |

把 409/404 也拿去重试，是这类桥接层最常见的实现 bug——它会把一次业务性拒绝放大成三次无谓的请求，并且让用户多等三倍时间才拿到本来立刻就能给出的答复。

## 验收标准

跑 `bash verify.sh`，8 项全部 OK 且退出码 0。

1. **夹具与证书完整** — 3 张证书齐备，测试集 10 条
2. **工具可发现且描述合格** — `list_tools` 返回 3 个工具；每个描述都要说清适用场景、不适用场景、参数格式、错误返回。这一项由 `verify.sh` 直接断言工具 schema，不经过你写的检查脚本
3. **三个工具端到端穿透** — 真正调到 mTLS ERP，ERP 侧确认身份来自 `mcp-bridge-01` 证书
4. **凭据不泄漏到模型侧** — 工具入参 schema 里不得出现任何凭据类参数，描述里不得出现证书路径
5. **重试生效** — 注入 2 次 503，工具最终成功，且 ERP 侧统计显示确实被打了 ≥3 次
6. **超时降级** — ERP 睡 5 秒，工具须在预算内返回结构化错误，不抛异常、不崩溃
7. **熔断生效** — 连续失败达阈值后快速失败，且不再打 ERP（统计数字不再增长）
8. **工具选择准确率** — 有 `DEEPSEEK_API_KEY` 时跑真实模型：≥8/10 正确，且**危险项零误触发**（3 条诱导性请求一次都不许调 `approve_order`）；无 key 时降级为更严格的静态描述质量检查

第 8 项的两档标准是有意的：没有 API key 也要能跑完这个 Lab，但要诚实标明跑的是哪一档。危险项零容忍不设百分比——**不可逆操作误触发一次就是事故**，没有"通过率 90%"这种说法。

## 探针 CLI 契约

`verify.sh` 通过这两个命令行工具驱动验收。你的实现必须按下面的格式输出，否则验收脚本读不懂。

`python3 -m src.check_tools --mode <M> --erp <URL>`：

| `--mode` | 期望 stdout | 说明 |
|---|---|---|
| `dump` | 一个 JSON 数组，每项含 `name` / `description` / `input_schema` | 供验收脚本断言描述质量与凭据泄漏 |
| `invoke` | `query=OK note=OK approve=OK cn=mcp-bridge-01` | 三个工具各真实调用一次；`cn` 取自 ERP 返回的证书身份 |
| `retry` | `result=ok erp_attempts=3` | `erp_attempts` 从 ERP 的 `_stats` 读，不是自己数的 |
| `degrade` | `error=upstream_timeout retryable=true raised=no` | `raised=no` 表示工具没有把异常抛给调用方 |
| `breaker` | `tripped=yes erp_total_at_trip=N post_trip_calls=5 fast_fail_ms=3` | 熔断后再打 5 次，报告熔断那一刻 ERP 的累计调用数 |

`python3 -m src.tool_select --erp <URL> --cases fixtures/tool_selection.jsonl`：

```
correct=9/10 danger_violations=0 mode=api
```

`danger_violations` 统计的是 `danger: true` 的用例里调用了 `forbid` 工具的次数。

注意 `dump` 模式输出的必须是**纯 JSON**，别在前面打印日志——验收脚本直接拿它喂 `json.load`。

## 可替换组件

这套技术栈不是唯一解，换掉任何一个都不影响 Lab 要教的东西：

| 本 Lab 用的 | 可换成 | 换的时候注意 |
|---|---|---|
| `mcp` 2.0.0 | `mcp>=1.28,<2` | v1 的类名是 `FastMCP`，导入路径 `mcp.server.fastmcp` |
| 进程内 `Client` | stdio / Streamable HTTP 传输 | 换传输层后验收脚本要起子进程，`run()` 的参数也不同 |
| DeepSeek | 任何支持 function calling 的模型 | 只需换 `tool_select.py` 里的 endpoint 与鉴权 |
| 标准库 `http.client` | `httpx` / `requests` | 遗留环境常常装不了额外依赖，这是选标准库的原因 |
| mTLS | 内部 token / IP 白名单 | 桥接层的抽象边界不变：模型侧一律不可见 |
| 自研熔断 | `pybreaker` 等 | 注意熔断状态是否跨线程共享 |

## 运行

```bash
bash fixtures/gen_certs.sh          # 首次运行需要
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt     # 系统 pip 会被 PEP 668 拦住，必须用 venv
bash verify.sh
```

`verify.sh` 会自己拉起 mock ERP 并在退出时清理。

测退出码时不要放进管道：`bash verify.sh > /tmp/v.log 2>&1; echo $?`
（`verify.sh | tail; echo $?` 拿到的是 `tail` 的退出码，不是验收结果。）

## 故障排查

**`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`**
装到了 v2 但代码是照 v1 写的。要么改导入路径，要么锁 `mcp>=1.28,<2`。

**`error: externally-managed-environment`**
PEP 668。建 venv，别用 `--break-system-packages` 去怼系统 Python。

**`[3/8]` 报 `SSLError: certificate verify failed`**
先跑 `bash fixtures/gen_certs.sh`。证书是 gitignore 的，克隆下来不会自带。

**`[5/8]` 重试项显示 `erp_attempts=1`**
重试没生效，或者你把 503 当成了不可重试的错误。检查失败分类逻辑。

**`[7/8]` 熔断后 ERP 累计数还在涨**
熔断没真正短路，只是记了个状态还在继续发请求。熔断的意义就是不再打下游。
注意这一项的「有没有再打 ERP」是 `verify.sh` 自己向 ERP 取数核对的，
不采信探针自报——被测方自报的数字不能用来给自己判分。

**`[8/8]` 危险项误触发**
模型把"帮我处理一下"理解成了审批。回到 `approve_order` 的 docstring——它有没有明确写"仅在用户明确表达审批授权时调用，模糊表述如'处理一下'不构成授权"。这一项失败几乎总是描述问题，不是模型问题。

## 延伸练习

1. 把 `approve_order` 改造成两段式：先返回待确认摘要，拿到二次确认才真正提交。对比改造前后危险项的表现。
2. 给三个工具加上不同的超时预算（查询 2 秒、写入 3 秒、审批 5 秒），验证预算确实是分别生效的。
3. 把熔断从"全局一个"改成"按 ERP 端点各一个"，验证查询接口熔断时审批接口仍可用。
