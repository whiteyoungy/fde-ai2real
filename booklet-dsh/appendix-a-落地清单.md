# 附录 A · 落地清单

按导读里那三档拆开。**每一步都给验证方式——没验证的那一步不算做完。**

> 本附录的命令取自官方文档 [1][2]。**本册没有在真实现场逐条实测**，
> 第一次执行请在自己的机器上做，别在客户环境里第一次跑。

---

## 零、先跑起来

装 Node.js，然后：

```sh
npx @deepseek-ai/dsh web
```

默认在 `http://127.0.0.1:3080` 起 Web 界面。本机启动会用默认浏览器打开页面；
**通过 SSH 启动时只打印宿主机 URL**，因为本地转发地址在你的 SSH 客户端或编辑器手里。
`--no-open` 只跑服务器不开浏览器 [1]。

从源码跑：

```sh
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh web
```

`pnpm run build` 准备仓库产物；`pnpm dsh web` 直接用这些已构建产物，不会重新构建 [1]。

**验证**：浏览器打开那个地址，页面出来了。

**进场前先查的两件事**（第 2 章 2.6 节）：

- [ ] Node 版本对得上 `^22.19.0 || >=24.0.0`
- [ ] 走 Python SDK 的话：Python ≥ 3.10，系统是 Linux x64／arm64 或 macOS 14+ arm64

---

## 一档 · 当工具用

目标：在你的环境里，用你能拿到的模型，把它跑通。

### A1. 接模型

**公有云 DeepSeek**：设置 → 模型 → DeepSeek 卡片填 API 密钥，保存。
密钥只写，页面之后只会收到脱敏描述符 [1]。

**企业网关或自建端点**：设置 → 模型 → 添加自定义提供方。填小写 Provider ID、
基础 URL、API 协议、凭据、至少一个模型 [1]。

> ⚠️ **Provider ID 是永久的**，请求、已保存会话、模型默认值和凭据引用都用它。
> 要改名只能新建一个再删掉旧的 [1]。**第一次就想清楚这个 id 叫什么。**

**验证**：发一条消息，收到回复。

### A2. 请求被拒时，先上这两个开关

改 `$DSH_HOME/settings.yaml`（**设置页面里没有这两个字段**）：

```yaml
llm-pi-ai:
  providers:
    my-gateway:
      apiKeyEnv: GATEWAY_API_KEY
      api: openai-completions
      baseURL: https://gateway.example/v1
      compat:
        supportsDeveloperRole: false
        maxTokensField: max_tokens
      models:
        - id: my-model
```

**验证**：能收到回复。收到之后**逐个撤掉再试**，搞清楚到底哪一个是必需的——
写进交付材料的应该是必需的那些，不是全都开着。

**只有推理模型失败** → 就是 `supportsDeveloperRole`，不用查别的 [1]。

### A3. 排障顺序（贴在值班手册上）

```text
1. MISSING_CREDENTIAL     → 存密钥，或提供被引用的环境变量
2. curl 打不通 baseURL     → 网络／代理／证书，停在这里查
3. UNKNOWN_MODEL          → 选已配置的模型，或给自定义提供方补上
4. 获取可用模型 401        → 密钥问题
   获取可用模型 404        → 没有 GET /models 端点，手动录入即可，不是故障
5. 前四步都对但请求全被拒  → 请求形状不对，回 A2
6. 只有推理模型失败        → developer 角色
7. 某开关因没有值被拒      → 冒号后面补值，或删掉这个键
```

### A4. 确认密钥没落进配置文件

```sh
grep -rn "sk-" $DSH_HOME/settings.yaml
```

**期望输出：什么都没有。** 配置里应该只有环境变量名（凭据引用），
值在 `$DSH_HOME/.credentials.yaml` 里 [1][3]。

### A5. 记下这台机器的沙箱强制力等级

在目标机器上执行一次需要沙箱的操作，确认后端报告的是 `full` 还是 `partial`。

**拿到 `partial` 的常见原因**：较旧的 Landlock ABI，或 Windows ACL 运行器的
Everyone 与硬链接边界 [4]。

**验证**：这个等级、内核版本、日期，三样一起写进交付材料。
**这是证据，不是配置。**

---

## 二档 · 当组件改

目标：能改造它，而不是只能配置它。

### B1. 把配置树打出来，存进仓库

```sh
dsh --profile web --dump-config > config-dump-$(date +%F).txt
```

**它打印出的任何条目，都可以由你自己的 patch 替换** [5]。

**验证**：文件存在，进了版本库，注明了版本号和日期。

### B2. 写第一份 patch

叠加顺序（越靠后越有话语权）[5]：

```text
1. profile 列出的组合包，按顺序
2. profile 自己的 cordis.patch.yml
3. Harness home 级的那份
4. 命令行 --patch 传进来的 overlay
```

> ⚠️ **patch 替换的是整个 config，不是逐字段合并** [5]。
> 先从 B1 那份 dump 里把目标条目的完整 config 抄出来，改完整条写回去。

**验证**：改完再跑一次 `--dump-config`，diff 出来的正好是你想改的那些，
**没有多出你没打算改的字段**。

### B3. 无头模式跑一次

```sh
dsh --profile headless "列出当前目录下的文件"
echo "退出码：$?"
```

预期行为 [6]：

- stdout 是最后一条非空 assistant 文本
- **退出码 0 表示最终轮次正常结束，1 表示没有**
- **成功运行时 stderr 是空的**
- **进程不打开监听端口**

**验证**：`echo $?` 给出 0；`2>/dev/null` 和不加的输出一样（说明 stderr 确实空着）。

### B4. SDK 接进自己的程序（可选）

```python
from deepseek_harness import DeepSeekHarness

with DeepSeekHarness(
    provider="deepseek-official",
    model="deepseek-v4-flash",
    cwd="/absolute/path/to/workspace",
    session_root="/absolute/path/to/sessions",
    cordis="/path/to/your.cordis.yml",
) as harness:
    result = harness.run("……", session_id="smoke-001")
print(result.final_response)
```

**验证**：`session_root` 下出现 JSONL 日志，里面能看到组装后的模型请求和工具调用 [2]。
**看到这个，说明第 4 章那套留痕在这条路上一样有。**

---

## 三档 · 当交付物给出去

目标：你撤场之后，它还活着，而且有人管。

### C1. 现场配置和开发配置分成两份

```text
patch/dev.cordis.patch.yml
patch/site-<客户简称>.cordis.patch.yml
```

启动时用 `--patch` 指定。**哪一份被加载了，是命令行上看得见的事实**，
不靠人记得改回去。

**验证**：用现场那份启动，`--dump-config` 的输出里没有任何开发用的条目。

### C2. 交付材料里放 diff，不放描述

补丁前后各一份 `--dump-config`，**diff 就是这次改了什么。**

**验证**：把这份 diff 交给一个没参与过的同事，他能说出你改了哪几件事。

### C3. 护栏逐条故意触发一次

每一条护栏——沙箱、审批策略、每一个钩子——**都要有一次故意触发的验证**，
看到它真的拦住了，再写进交付材料。

**尤其是钩子桥接**：`http`／`mcp_tool`／`prompt`／`agent` 类型的钩子
会被解析后**跳过，只记一条警告** [7]。你以为在拦，其实没在拦。

**验证**：每条护栏一条命令 + 一段预期的拒绝输出，成对写进材料。

### C4. 三段式写数据流向

不要合并成一句。分三段写：

1. **文件边界**——沙箱模式是哪一档，强制力等级是什么（A5 那个值）。
2. **网络边界**——沙箱不管网络 [4]；出网靠出口代理／网络命名空间／主机防火墙，归客户网络组。
3. **模型通道**——模型请求本身要不要出网，取决于模型部署在哪。**这是数据边界。**

再加两项，如果用到了：

- 遥测后端的 `sharing` 披露值 [8]——它是强制披露的，写进材料。
- 用了 Claude Code 子 agent 提供方的话：**它会读宿主机上现有的用户、项目、
  本地 Claude 设置，包括原生账户状态** [9]。这条必须主动说明。

### C5. 采下第一条回归用例

按第 5 章那四步：

```text
1. 故障还热着时，先记会话 id（在回“我看一下”的同时贴出来）
2. 修完之后取三样：那一轮的边界、当时的 current 投影、出问题的工具调用与返回
3. 写判据，不写期望输出
4. 挂进能自动跑的地方（B3 那条命令）
```

**验证**：把代码回滚到修复之前，**这条用例必须失败。** 不失败就是没抓住。

### C6. 接管清单

| 留什么 | 长什么样 | 验证 |
|---|---|---|
| 现在实际跑的是什么 | `--dump-config` 输出，带版本和日期 | 文件在客户仓库里 |
| 这次改了什么、为什么 | 现场 patch，带提交信息 | git log 能看到 |
| 怎么验证它还好着 | 一条无头模式命令 | 退出码即结论 |
| 出事怎么退回去 | 回滚脚本 + 删哪份 overlay | **演练过一次** |
| 判据在哪 | 验收集，存客户环境 | 客户能自己跑起来 |
| 谁维护 | **一个人名** | 那个人知道自己是那个人 |

**最后一行的验证方式不是玩笑。** “交给运维部”不是接管，是弃养——
上册第 10 章讲第 6 关 采用讲的就是这件事。

### C7. 撤场前问自己三句

1. 除了我，还有几个人能改这套配置？
2. 如果三年后这个项目不维护了，客户手上还剩下什么？
3. **合同的运维期，和它的版本节奏，哪个更长？**（第 7 章 7.1 节）

---

## 参考来源

1. DeepSeek Harness 仓库首页中文说明（`README.zh.md`）与
   《配置模型》用户指南（`docs/user/guide/providers.zh.md`），
   仓库提交 `b150a551`，检索于 2026-08-24。
2. 《Python SDK 快速上手》（`docs/user/guide/python-sdk.zh.md`），同一提交。
3. 凭据子系统文档（`docs/subsystems/credentials.zh.md`），同一提交。
4. 进程沙箱子系统文档（`docs/subsystems/sandbox.zh.md`），同一提交。
5. 架构文档（`docs/architecture.zh.md`），同一提交。
6. 无头组合包说明（`packages/bundle/headless/README.zh.md`），同一提交。
7. Claude Code 钩子桥接说明（`packages/hooks/hooks-claude-code/README.zh.md`），同一提交。
8. 遥测子系统文档（`docs/subsystems/session-telemetry.zh.md`），同一提交。
9. Claude Code 子 agent 提供方说明（`packages/subagent/subagent-claude-code/README.zh.md`），同一提交。
