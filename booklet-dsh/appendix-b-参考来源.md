# 附录 B · 参考来源

## 怎么自己复核这一册

本册所有关于 `dsh` 行为的陈述，都取自仓库的一个确定提交。
**复核方式是三条命令**，不需要跑起来：

```sh
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
git checkout b150a551b8d465e31e418e1b2eaf5e79bbb7d28e
```

然后按下面的文件路径去看。仓库里的文档是中英双语配对维护的，
`.zh.md` 是中文侧，本册引的都是中文侧。

**对不上的时候**，先确认你是不是在这个提交上。这个项目处于开发者预览阶段，
官方明说会有破坏性变更 [A1]——**行为变了是预期之内的事，不是本册写错了。**
真发现本册写错了，那是本册的问题，请以仓库为准。

---

## 一手来源：仓库文件

以下全部位于 `deepseek-ai/deepseek-harness`，提交
`b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`（2026-08-21，`v0.1.1-rc.2`），
**检索于 2026-08-24**。

仓库地址：[https://github.com/deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)

### 项目层

| 编号 | 文件 | 本册用它说明什么 |
|---|---|---|
| A1 | `README.zh.md` | 一切皆插件、Cordis、开发者预览声明、运行方式 |
| A2 | `LICENSE` | MIT |
| A3 | `package.json` | 版本 `0.1.1-rc.2`、`engines.node` 为 `^22.19.0 \|\| >=24.0.0` |

### 架构与核心

| 编号 | 文件 | 本册用它说明什么 |
|---|---|---|
| A4 | `docs/architecture.zh.md` | 插件树叠加顺序、seam 三角色、`--dump-config`、组合包职责、**模型可见即已记录**、三种事件域、轮次流程 |
| A5 | `docs/subsystems/invariants.zh.md` | 不变量服务；检查可以断言什么、不能断言什么 |
| A6 | `docs/subsystems/session-query.zh.md` | `current`／`shadowed`／`log-only` 三分法 |
| A7 | `docs/subsystems/persistence.zh.md` | 崩溃恢复不截断日志、合成的 `interrupted` 结束原因、JSONL 与 SQLite 后端 |

### 控制与护栏

| 编号 | 文件 | 本册用它说明什么 |
|---|---|---|
| A8 | `docs/subsystems/sandbox.zh.md` | 三档沙箱模式、**网络与进程可见性不在其定义范围内**、`full`／`partial` 强制力、逐调用策略、`SANDBOX_UNAVAILABLE`、工作区根规范化 |
| A9 | `docs/subsystems/approval.zh.md` | 四值闭合结果、`unavailable` 的产生条件、`never` 在分发之前执行、审批审计事件对 |
| A10 | `docs/subsystems/permission-presets.zh.md` | 预设不拥有强制执行、`custom` 是派生状态 |
| A11 | `docs/subsystems/credentials.zh.md` | 凭据引用而非值、每次操作重新解析、进程环境供值时 `writable: false` |

### 留痕与遥测

| 编号 | 文件 | 本册用它说明什么 |
|---|---|---|
| A12 | `docs/subsystems/session-telemetry.zh.md` | 边界公理（职责止于 `emit()`）、尽力而为投递、按 `(session.id, event.seq)` 去重、`seq` 缺口是常态、`sharing` 强制披露 |
| A13 | `packages/hooks/hook-protocol/README.zh.md` | `hook/invoked` 与 `hook/result` 成对、必须位于未结束的轮次内、`SessionStart` 没有 `hook/*` 记录 |
| A14 | `docs/tool-catalog.zh.md` | 模型可见的工具清单，含 `session_search` 一族。**该文档由脚本从源码生成并有新鲜度校验** |

### 模型接入

| 编号 | 文件 | 本册用它说明什么 |
|---|---|---|
| A15 | `docs/user/guide/providers.zh.md` | **`compat.supportsDeveloperRole` 与 `compat.maxTokensField`**、模态声明、断言而非检查、排错表、Provider ID 永久性 |
| A16 | `docs/user/guide/python-sdk.zh.md` | SDK 用法、平台与 Python 版本要求、安装后不需要系统 Node.js |
| A17 | `packages/llm/llm-deepseek/README.zh.md` | DeepSeek 适配器配置面 |
| A18 | `docs/config-catalog.zh.md` | 自动生成的配置目录，`PiAiCompatProfile` 段列出全部兼容开关 |

### 交付形态

| 编号 | 文件 | 本册用它说明什么 |
|---|---|---|
| A19 | `packages/bundle/headless/README.zh.md` | 退出码约定、stdout／stderr 约定、不开监听端口、两条已知限制 |
| A20 | `packages/hooks/hooks-claude-code/README.zh.md` | 兼容路径定位、只跑命令钩子、其他类型被跳过、`configPath` 进程级 |
| A21 | `packages/hooks/hooks-codex/README.zh.md` | 十个钩子点里的五个、仅正则 matcher、没有工具前审批或改写路径 |
| A22 | `docs/subsystems/subagent.zh.md` | 多提供方并存、`UNSUPPORTED_CAPABILITY` 明确拒绝而非静默忽略 |
| A23 | `packages/subagent/subagent-claude-code/README.zh.md` | **会读宿主机常规的用户、项目、本地 Claude 设置，包括原生账户状态** |

---

## 二手／转引

| 编号 | 来源 | 说明 |
|---|---|---|
| B1 | Cordis 框架仓库 [https://github.com/cordiverse/cordis](https://github.com/cordiverse/cordis) | **本册未阅读其文档正文**，只经 `README.zh.md` 转引其定位 |
| B2 | 论文《A Programming Paradigm for Spatiotemporal Composability》[https://github.com/cordiverse/paper](https://github.com/cordiverse/paper) | **本册未阅读原文**，只经 `README.zh.md` 转引其存在与题名 |

---

## 本书自己的内容

以下**不是** DeepSeek Harness 的主张，是本书的判断或推论。引用时请注明来源是本书。

| 位置 | 内容 |
|---|---|
| 第 1 章 1.4 节 | “可配置”与“可替换”在评审会上的差别，及那张对比表 |
| 第 2 章 2.5 节 | 那个七步排障顺序（前四条的错误码来自 A15，**顺序是本书排的**） |
| 第 3 章 3.2 节 | 把强制力等级归入四层骨架的证据层；`partial` 的三条应对路径 |
| 第 3 章 3.5 节 | “看旋钮不看预设名”这条评审规矩 |
| 第 4 章 4.5 节 | “本地日志是账本，遥测是仪表盘”的定位，及方案写法 |
| **第 5 章全章** | **把会话日志用作验收集原料**——这一整章都是本书推论，官方文档从未这样主张 |
| 第 6 章 6.1 节 | 两份 patch 的做法、交付材料放 diff |
| 第 7 章 7.1 节 | 破坏性变更的三项成本结构 |
| 第 7 章 7.2、7.3 节 | 那两张判断表 |
| 第 7 章 7.5 节 | 四层骨架与这套工具的对应关系 |

---

## 本册没有做的事

按本书的规矩，把没做的写出来：

- **没有在真实客户现场部署过这套东西。** 第 2、3、6 章的现场判断来自本书其他章节的
  一般经验，不是对这个具体工具的现场实测。
- **没有实测那两个 `compat` 开关。** 它们取自官方指南并逐字对照过，但没在真实网关上验证。
- **没有验证“模型可见即已记录”那条不变量在被违反时的实际行为。**
  本册只能说官方文档这样声明，并且仓库里有一个不变量服务。
- **没有经历过一次它的破坏性升级**，所以第 7 章那三项成本是结构分析，不是实测数据。
- **没有读 Cordis 的论文和框架文档**，只用了 `dsh` 仓库里对它的转述。
- **没有做性能、能力或与其他产品的对比评测。** 它现在是预览版，
  拿预览版做能力评测对谁都不公平，而且那类结论三个月过期一次。

---

## 本书内部引用

本册引用到的本书章节，列在这里，方便回查：

| 引用位置 | 讲什么 |
|---|---|
| 上册第 9 章 | 四层骨架、六道关卡 |
| 上册第 3 章 | 选型判断、不该引用的数字 |
| 上册第 11 章 | 第 2 关 定界，写不下来的边界等于不存在 |
| 上册第 15 章 | 第 6 关 采用，采用率崩塌的死法 |
| 上册第 6 章 | 经验资产化、三类交付结果的回收 |
| 下册第 1 章 | 底座与现场层的物理边界 |
| 下册第 3 章 | Spec Kit／OpenSpec／Superpowers 各补什么 |
| 下册第 6 章 | 企业集成、客户 IT 部门的话怎么翻 |
| 下册第 4 章 | 换 embedding 模型要全量重建索引 |
| 下册第 10 章 | 部署护栏与可观测性、命令不由你来敲的时候 |
| 下册第 8 章 | 评估的工程实现、验收集三件套 |
| 下册第 13 章 | 信创适配 |
| 别册一第 5 章 | Codex 只支持 Responses 协议这个坑 |
| 别册一第 6、7 章 | 当成可交付组件、harness 工程与本书的关系 |
