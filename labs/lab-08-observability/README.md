# Lab-08 · 可观测性、日志脱敏与成本看板

**关联章节**：下册第 7 章 §7.5（可观测性接入、日志脱敏、成本看板）
**预计耗时**：4–6 小时

## 为什么这个 Lab 不自建 Langfuse

下册第 7 章 13.5 节自己给出了理由：自托管 Langfuse 依赖 Postgres + ClickHouse + Redis + MinIO 四个有状态服务，官方最低建议 **4 vCPU / 16GiB RAM / 100GiB 存储**；如果只是要验证「埋点能不能跑通」，本地 mock 比自建一套 ClickHouse 集群划算得多。

本 Lab 就走这条路：**用真实的 Langfuse Python SDK（v4.14.3），把它指向一个本地 mock 摄取端**。SDK v4 起基于 OpenTelemetry 重写，上报走标准 OTLP/protobuf，端点是 `/api/public/otel/v1/traces`——mock 端只要能收 OTLP 并解出 span 就够了。

**埋点代码是真的，SDK 是真的，上报的字节是真的；只有存储后端是假的。** 这个 Lab 要练的三件事——trace 结构设计、脱敏时机、成本归因——恰好全都在 SDK 侧完成，与后端是 ClickHouse 还是 mock 无关。

真正只有自建 Langfuse 才能验的东西（UI 交互、ClickHouse 查询性能、告警规则）不在本 Lab 范围内，README 末尾给了切换到真实后端的步骤。

## 这个 Lab 要解决什么

三件在现场都会被客户问到、且都容易做错的事：

**一、trace 要长成什么样。** 一次「回答用户问题」在系统里是好几步（检索、生成、可能还有重排）。如果每一步各报各的、彼此没有父子关系，出问题时你只能看到一堆孤立事件，没法回答"这次回答慢在哪一步"。

**二、脱敏必须在上报之前。** 这是本 Lab 的核心。下册第 7 章原文说得很重："脱敏后的日志才允许写入持久化存储或转发给 Langfuse——**这一步顺序不能反**"。顺序反了的后果不是"日志里有敏感信息"这么轻——是**你把客户的个人信息发给了第三方 SaaS**，而且发出去就收不回来了。

**三、成本要算到业务动作上，不是算到 token 上。** 「这个月花了 800 块」对业务方没有意义。「每处理一张工单花 0.06 元」才有意义，因为它能和人工成本比。

## 脱敏这一项为什么设成零容忍

`verify.sh` 第 4 项直接在**原始上报字节**上搜敏感串，一次出现就判失败，不设比例。

不在解码后的字段上搜，是因为那样验不住：一个把 PII 塞进未被解析字段、或者塞进异常堆栈、或者塞进 span 名字的实现，字段级检查会全部放行，而字节照样发出去了。

零容忍也不是苛刻。脱敏漏一次和漏一百次，在合规上是同一件事——数据已经出境了。这和下册第 8 章说的「高危项不设通过率」是同一个道理。

## 但只查「漏没漏」是不够的

只有第 4 项的话，最省事的实现是把整段文本全掩掉。所以有第 5 项：**`must_keep` 里的业务字段必须仍然可见**。

`fixtures/pii_cases.jsonl` 里 8 条用例，其中两条（`p07`、`p08`）**完全不含 PII**，全是错误码、工单号、预算编号和大额数字——正是粗暴正则最容易误伤的形态。还有一条（`p06`）把手机号和订单号、金额混在同一句里，考验的是脱敏的精度而不是力度。

掩得太狠的代价是真实的：一份把订单号也打成 `****` 的 trace，排障时等于没有。

## 目录结构

```
lab-08-observability/
├── README.md
├── requirements.txt
├── verify.sh
├── fixtures/
│   ├── mock_langfuse.py         # 本地 OTLP 摄取端，暴露 /_spans 与 /_raw
│   ├── pii_cases.jsonl          # 8 条：6 条含 PII + 2 条纯业务（防过度脱敏）
│   └── pricing.json             # 单价表与业务动作定义
├── src/                         # 你要实现的部分
│   ├── redact.py                # 脱敏中间件，必须在上报前生效
│   ├── app.py                   # 被观测的流水线：检索 → 生成
│   └── cost.py                  # 成本归因与看板
└── results/                     # 运行产物（已 gitignore）
```

## 探针 CLI 契约

- `python3 -m src.app --ingest URL --cases fixtures/pii_cases.jsonl`
  → `traces=8 spans=N generations=N`
- `python3 -m src.cost --ingest URL --pricing fixtures/pricing.json --out results`
  → 打印每次调用成本与按业务动作聚合的看板，末行 `actions=N calls=N total_cny=..`
  → 同时写出 `results/cost_report.json`，含 `by_action.<动作>.{calls,total_cny,avg_cny}`

## 验收标准

跑 `bash verify.sh`，7 项全部 OK 且退出码 0。

1. **夹具与 SDK 就位** — 8 条用例、单价表、langfuse SDK 可导入
2. **mock 摄取端可用** — 能收 OTLP 并解出 span
3. **trace 结构完整** — 一次调用的所有 span 共享同一 `trace_id`，有且仅有一个根 span，生成步骤标为 `generation` 类型
4. **PII 零泄漏** — 原始上报字节里不得出现任何 `must_mask` 值。**一次即失败**
5. **脱敏不过度** — 所有 `must_keep` 业务字段在 span 属性里仍可见
6. **每次调用成本可见且算得对** — 生成类 span 带 token 数与成本，`verify.sh` 按单价表独立重算并核对
7. **成本看板按业务动作聚合** — 输出每个业务动作的调用次数、总成本、单次均价

第 4、5 项必须一起看。单独任何一项都能被极端实现骗过：只看第 4 项就全掩，只看第 5 项就不掩。

## 两档运行

| 档位 | 生成后端 | 说明 |
|---|---|---|
| 有 `DEEPSEEK_API_KEY` | deepseek-chat | 真实 token 数与真实成本 |
| 无 key | 本地 Ollama `qwen2.5:0.5b` | token 数为真，API 成本为 0 |

无 key 档的成本为 0 不代表零成本——**本地推理的机器折旧与电力要在别处核算**，`pricing.json` 里对此有注记。成本看板最常见的误导就是把"没有 API 账单"说成"不花钱"。

## 可替换组件

| 本 Lab 用的 | 可换成 | 注意 |
|---|---|---|
| mock 摄取端 | 真实自托管 Langfuse / Langfuse Cloud | 见下节；埋点代码一行不用改 |
| 正则脱敏 | NER 模型（人名、地址） | 下册第 7 章建议正则打头阵、NER 兜底自由文本。本 Lab 只做正则档，姓名与地址靠词表，**这在真实语料上不够** |
| Langfuse SDK | 原生 OpenTelemetry SDK | v4 本来就是 OTel，换掉只是少了 Langfuse 的语义约定 |
| 硬编码单价表 | 从厂商定价页定期同步 | 单价写死是成本看板最常见的失效原因 |

## 切换到真实 Langfuse

```bash
# 官方 docker compose（需要 4 vCPU / 16GiB RAM 量级的机器）
git clone https://github.com/langfuse/langfuse && cd langfuse
docker compose up -d
```

然后把 `LANGFUSE_HOST` 指向它，`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 换成项目里生成的真实密钥。**`src/` 下的代码一行都不用改**——这正是把 mock 做在摄取端而不是 SDK 层的好处。

**这一节没有实测数据。** 本书写作环境是 2 核 / 3.9GB 内存，跑不起这套，上面的命令取自官方仓库说明，没有跑过。

## 运行

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
bash verify.sh
```

`verify.sh` 会自己拉起 mock 摄取端并在退出时清理。

测退出码不要放进管道：`bash verify.sh > /tmp/v.log 2>&1; echo $?`

## 故障排查

**第 3 项：span 没有共同的 trace_id**
每个函数各自建了新 trace。要让子步骤在父 span 的上下文里执行——用 `@observe` 装饰嵌套调用，不要在每步手动新建 trace。

**第 4 项：PII 仍出现在原始字节里**
脱敏放在了上报之后，或者只脱了 `input` 没脱 `output` 与异常信息。检查所有会进 span 属性的路径。

**第 5 项：业务字段被掩掉了**
正则太宽。`\d{11}` 会吃掉 11 位的任何数字，`\d{6,}` 会吃掉金额。手机号要带号段约束，身份证要带日期段结构。

**第 6 项：成本对不上**
单价表的单位是**每百万 token**，不是每千 token。

## 延伸练习

1. 给 `p05`（住址 + 姓名）换十个不同写法的地址，看正则档还能拦住几个。这就是下册第 7 章说「NER 兜底自由文本」的原因。
2. 在成本看板里加一列「单位业务成本相对人工成本的比值」，需要你自己定义人工基线。哪一列更容易说服业务方？
3. 故意把脱敏中间件挪到上报之后，跑一次第 4 项，确认它真的会失败。**一个不会失败的检查等于没有这个检查。**
