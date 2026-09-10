# 附录 B · 参考来源

本册沿用全书的**可信度分层**约定：

> **一手可验证** > **多源交叉** > **二手推测** > **笼统说法（不采信）**

每一条都标了它属于哪一层。凡是标了“二手转述”的，
意味着本书**没有逐字核对原始出处**，引用时请自行复核。

所有链接的访问时间为 **2026 年 8 月**。开源项目变化快，
尤其是配置键名和命令行开关——**用之前请以你手上那个版本的
`codex --help` 和 `codex doctor` 输出为准。**

---

## 一手可验证 · 源码与仓库内文档

这一层的内容直接来自 `openai/codex` 仓库，可以自己 clone 下来核对。

**[1] Codex 仓库主页与 CLI 子命令**
<https://github.com/openai/codex>
许可证 Apache-2.0，主语言 Rust。子命令清单取自
`codex-rs/cli/src/main.rs` 的 `Subcommand` 定义。
本册引用的具体事实：许可证、语言、`codex mcp-server`、`codex doctor`、
`codex resume` / `fork` / `archive`、`codex execpolicy`、`codex app-server`。

**[2] 执行策略引擎（execpolicy）**
<https://github.com/openai/codex/blob/main/codex-rs/execpolicy/README.md>
`prefix_rule` 的字段、三档 `decision`、`match` / `not_match` 的加载期校验、
`host_executable` 的路径约束、`codex execpolicy check` 的用法。

**[3] app-server 协议**
<https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md>
JSON-RPC 2.0、四种传输方式、`generate-ts` / `generate-json-schema`、
健康探针 `/readyz` `/healthz`、过载错误码 `-32001`、
`RUST_LOG` 与 `LOG_FORMAT=json`。
**注意**：README 明确写了 websocket 传输“实验性、不受支持、
不要用于生产工作负载”。

**[4] 网络策略代理**
<https://github.com/openai/codex/blob/main/codex-rs/network-proxy/README.md>
HTTP 代理默认 `127.0.0.1:3128`、SOCKS5 默认 `127.0.0.1:8081`、
`mode = "limited"` 只读模式、HTTPS 中间人解密与 CA 私钥只驻内存、
`dangerously_allow_non_loopback_proxy` 默认关闭。

**[5] Linux 沙箱**
<https://github.com/openai/codex/blob/main/codex-rs/linux-sandbox/README.md>
bubblewrap 为默认文件系统沙箱、找不到 `bwrap` 时的回退与启动警告、
**user namespace 建不了时同样只给警告**、WSL1 不支持、
`features.use_legacy_landlock` 强制走 Landlock 老路径。
第 5 章 5.3 节那条“沙箱可能形同虚设”的判断，依据就是这份文档。

**[6] OpenTelemetry 集成**
<https://github.com/openai/codex/blob/main/codex-rs/otel/README.md>
`OtelProvider` / `SessionTelemetry` / `metrics`、
OTLP over HTTP 导出、日志与链路与指标三类。

**[7] Responses API 代理**
<https://github.com/openai/codex/blob/main/codex-rs/responses-api-proxy/README.md>
严格转发模型（只放行 `POST /v1/responses`，其余 403）、
**特权用户启动、从 stdin 读密钥**的部署模式、
`--http-shutdown` 与 `--server-info`、
配套的 `model_providers` + `profiles` 配置样例。

**[8] TypeScript SDK**
<https://github.com/openai/codex/blob/main/sdk/typescript/README.md>
`Codex` / `startThread` / `run` / `runStreamed` / `resumeThread`、
SDK 通过启动 CLI 并交换 JSONL 事件工作、
`outputSchema` 结构化输出、`env` 与 `config` / `configOverrides` 覆盖、
会话持久化在 `~/.codex/sessions`。
Python SDK 在同仓库 `sdk/python/`。

**[9] 模型提供方与 wire_api**
<https://github.com/openai/codex/blob/main/codex-rs/model-provider-info/src/lib.rs>
`wire_api = "chat"` 已移除，报错常量 `CHAT_WIRE_API_REMOVED_ERROR`
指向 <https://github.com/openai/codex/discussions/7782>；
内置 `ollama` / `lmstudio` 提供方同样以 `WireApi::Responses` 构造。
**第 5 章整章的立论基础就是这一条，建议自行 clone 核对。**

---

## 一手可验证 · 官方文档

仓库 `docs/` 目录下的文件基本都是指向官方文档站的跳转页，
正文在下面这些地址。原 `developers.openai.com/codex/*` 会 308 跳转到
`learn.chatgpt.com/docs/*`。

**[10] 非交互模式**
<https://learn.chatgpt.com/docs/non-interactive-mode>
`codex exec`、stderr/stdout 分流、`--json` 的 JSONL 事件格式、
`--output-schema`、`-o` / `--output-last-message`、`--ephemeral`、
`--skip-git-repo-check`、`--ignore-user-config`、`--ignore-rules`、
`resume --last`、管道输入的两种形态、
CI 中的双 job 密钥隔离做法、`openai/codex-action`。

**[11] 沙箱与审批**
<https://learn.chatgpt.com/docs/sandboxing>
<https://learn.chatgpt.com/docs/agent-approvals-security>
三档 `sandbox_mode`、三种 `approval_policy`、`approvals_reviewer`
（`user` / `auto_review`）、各平台强制机制、
`[sandbox_workspace_write] network_access`、常见预设组合。

**[12] AGENTS.md**
<https://learn.chatgpt.com/docs/agent-configuration/agents-md>
查找顺序与 override 优先级、**从仓库根往下拼接、近的覆盖远的**、
每层最多一个文件、`project_doc_max_bytes` 默认 32 KiB。

**[13] Skills**
<https://learn.chatgpt.com/docs/build-skills>
`SKILL.md` 与目录结构、frontmatter 的 `name` / `description`、
五个作用域路径（`.agents/skills`、`$REPO_ROOT/.agents/skills`、
`$HOME/.agents/skills`、`/etc/codex/skills`、内置）、
显式（`$skill`）与隐式两种触发方式、遵循开放 agent skills 标准。

**[14] 配置文件**
<https://learn.chatgpt.com/docs/config-file/config-basic>
<https://learn.chatgpt.com/docs/config-file/config-reference>
六层配置优先级、`~/.codex/config.toml` 与项目级 `.codex/config.toml`、
**项目标记为不可信时跳过整个项目层**、
`model_providers` 的 `base_url` / `env_key` / `wire_api`、
`mcp_servers` 的 `command` / `url` / `enabled` / `env` /
`enabled_tools` / `disabled_tools`、
`history.persistence` / `history.max_bytes`、
`default_permissions`、profiles。
`allow_managed_hooks_only` 只在 `requirements.toml` 里生效这一条，
另见仓库内 `docs/config.md`：
<https://github.com/openai/codex/blob/main/docs/config.md>

**[15] 企业托管配置**
<https://learn.chatgpt.com/docs/enterprise/managed-configuration>
`requirements.toml`（硬约束，用户不可覆盖）与
`managed_config.toml`（默认值）的区别、
三平台文件路径与 macOS MDM 键名、三种下发渠道、
可约束的键范围（审批策略、审批人、自动审查策略、沙箱模式、
权限档、联网搜索模式、托管钩子、可启用的 MCP 服务、插件市场源）。
另见管理员部署指南：
<https://learn.chatgpt.com/docs/enterprise/admin-setup>

**[16] 生命周期钩子**
<https://learn.chatgpt.com/docs/hooks>
事件名清单、`[[hooks.<Event>]]` 的 TOML 结构、`matcher`、
stdin JSON 的字段、`permissionDecision` / `permissionDecisionReason`、
**退出码 2 + stderr 作为拦截方式**、`additionalContext`。

**[17] 规则（execpolicy 的用户侧文档）**
<https://learn.chatgpt.com/docs/agent-configuration/rules>
`.rules` 文件位置（`~/.codex/rules/default.rules`、
`<repo>/.codex/rules/`）、Starlark 语法、
**多条命中时最严的赢**（`forbidden` > `prompt` > `allow`）、
复合命令的拆分规则与它的边界。

**[20] Codex 作为平台**
<https://developers.openai.com/blog/codex-as-a-platform>
OpenAI 官方开发者博客（本次抓取成功，属一手）。
“harness 管什么 / 应用管什么”的责任分界、
三种接入方式（`codex exec` / SDK / app-server）各自适合什么、
“把 agent 搬进为这份工作设计的软件里”这一主张、
以及包括报税在内的落地案例。
**其中“试点处理 7000 份报税表、准备时间减少约三分之一”
是厂商发布的单个试点数据，不是第三方核验的行业基准**，
本册在第 6 章 6.0 节已就此加了使用限制说明。

**[21] OpenAI 官方账号与 Greg Brockman 的相关发布（2026 年 8 月 20 日）**
<https://x.com/OpenAIDevs/status/2090230646497251387>
<https://x.com/gdb/status/2090246288478814281>
“应用掌控界面、上下文、工具和审批，harness 负责跑 agent 循环”这句表述出自前者。
**这两条社交媒体发布本身不作为独立证据**，
它们的实质内容即 [20] 那篇博客，引用时以博客为准。

---

## 二手转述 · 未逐字核对

**[18] OpenAI《Harness engineering: leveraging Codex in an agent-first world》**
<https://openai.com/index/harness-engineering/>
**本书写作时该地址对所用抓取方式返回 403，未能读到原文。**
第 7 章关于三人团队、五个月、一百万行代码、1500 个 PR 的数字，
以及五条原则的表述，均来自下面 [19] 的二手来源交叉整理。
**引用这些数字前请自行打开原文核对。**

相关的另一篇（同样未直接读到）：
《Unlocking the Codex harness: how we built the App Server》
<https://openai.com/index/unlocking-the-codex-harness/>

**[19] 关于 [18] 的二手报道与整理**
- <https://www.infoq.com/news/2026/02/openai-harness-engineering-codex/>
- <https://tonylee.im/en/blog/openai-harness-engineering-five-principles-codex/>
- <https://zby.github.io/commonplace/sources/harness-engineering-leveraging-codex-agent-first-world/>

第 7 章 7.3 节那五条原则的标题，是这些二手来源的**转述措辞**，
不是 OpenAI 原文的小标题。本书对它们做了进一步的中文改写
并映射到六道关卡——**映射关系是笔者归纳，不是原文观点。**

> **一条主动排除的引用**：检索过程中见到一条署名的 OpenAI 工程师引语，
> 内容与另一家同名产品（Harness）的宣传语高度雷同，
> 判断为二手来源的张冠李戴，本册不予采信、不予引用。
> 这正是“二手转述”这一层需要单独标出来的原因。

---

## 本书内部交叉引用

本册多处引用上下册正文，对应关系：

| 本册位置 | 引用的是 |
|---|---|
| 第 1 章 1.5 | 下册第 3 章（三套工具怎么选） |
| 第 2 章 2.3 | 上册第 13 章（第 4 关验收） |
| 第 2 章 2.5 | 上册第 18 章（合规与备案） |
| 第 3 章 3.1 | 上册第 3 章（常见死法） |
| 第 3 章 3.2 | 上册第 6 章（经验资产化） |
| 第 3 章 3.4 | 下册第 8 章（评估的工程实现） |
| 第 4 章 4.2 | 上册第 15 章（第 6 关采用）、下册第 10 章（可观测性） |
| 第 4 章 4.4 | 上册第 16 章（甲乙方关系与商务链路） |
| 第 5 章 5.1 | 上册第 11 章（第 2 关定界） |
| 第 5 章 5.2 | 上册第 17 章（国企银行政务交付） |
| 第 5 章 5.4 | 上册第 18 章（合规与备案） |
| 第 6 章 6.0 | 上册第 2 章（这个岗位在解决什么问题） |
| 第 6 章 6.3 | 下册第 6 章（企业集成）、下册第 14 章（案例一 · MCP） |
| 第 6 章 6.5 | 上册第 12 章（第 3 关切片） |
| 第 7 章 7.1 | 上册第 3 章（不该引用的数字） |
| 第 7 章 7.5 | 下册第 2 章（改动分档）、下册第 3 章（三套工具） |
| 附录 A | 上册第 14 章（第 5 关上线） |
| 导读 · 三条读法 | 下册第 2 章（按改动大小分档） |
