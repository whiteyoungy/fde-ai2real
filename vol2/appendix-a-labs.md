# 附录 A · 12 个 Lab 总清单

本书把动手部分拆成 12 个 Lab（Lab-01 至 Lab-12）。截至本版定稿，**12 个 Lab 均已有完整目录、实现代码、夹具与 `verify.sh`，并通过各自定义的验收路径**。验收并不等于所有硬件组合都已覆盖：CPU/GPU、真实 API/本地降级、国产加速卡等条件的差异，仍按各 Lab README 与下表的限定说明理解。

正文里还保留少量“未实测代码”标记。**这些标记不是说对应 Lab 没做，而是代码依赖通用 Lab 无法覆盖的现场条件**：例如真实外联地址审计、客户侧向量库硬接线和特定编排框架的合规节点。GPU 骨架只验证过 API 形态与小模型路径，不能外推为 7B 模型的显存与吞吐结论。

每一处的标注都写明了**缺的是什么条件**，而不是笼统一句“未实现”。这个区别对读者是实质性的：“你有 GPU 就能验”和“不知道能不能用”是两回事。回填过程中还修正了三处标注归属错误——代码块标着某个 Lab、而那个 Lab 根本不做这件事，这类错误会让代码永远等不到它等的那个验证。

## A.0 现状核查：怎么查、查到了什么

当前状态可以直接从仓库核查：

```bash
find labs -maxdepth 2 -name verify.sh | sort
find labs -maxdepth 2 -name README.md | sort
```

两条命令应各返回 12 项。真正的验收仍以进入对应目录运行 `bash verify.sh` 为准；需要 Docker、模型密钥或特殊硬件的路径，以 README 写明的前置条件和降级口径为准。不要把“仓库里有脚本”误写成“所有目标环境都已验证”。

## A.1 总表

| # | Lab 名称 | 归属章 | 产出物 | 状态 | 预计耗时 |
|---|---|---|---|---|---|
| Lab-01 | 脏 PDF 发票摄取管道 | 第 4 章、上册第 20 章 | 解析脏 PDF → Pydantic 强类型校验 → 校验失败回灌 Agent 上下文自纠错 → 输出合规 JSON | **已实现**（`verify.sh` 6/6，双路径均验证） | 4–6 小时 |
| Lab-02 | mTLS + OAuth2 认证桥接 | 第 6 章 | mock 遗留系统（要求 mTLS）+ 认证网关（对外 OAuth2、对内 mTLS）+ 凭据轮换演示 | **已实现**（`verify.sh` 7/7，40 并发跨轮换窗口 failures=0） | 4–6 小时 |
| Lab-03 | 遗留 API 封装为 MCP Server | 第 9、14 章 | MCP Server 暴露查询/写入/审批三个工具，含鉴权桥接、重试、降级 | **已实现**（`verify.sh` 8/8，工具选择 10/10、危险工具零误触发） | 6–8 小时 |
| Lab-04 | 混合检索 RAG + 质量诊断 | 第 4、9、17 章 | BM25 + 向量 + RRF + Rerank 完整链路，附检索质量三分法诊断脚本 | **已实现**（`verify.sh` 7/7，混合 58/59 对纯向量 53/59） | 8–10 小时 |
| Lab-05 | 企业 Evals 框架 + CI 门禁 | 第 8 章 | 三层评估集（黄金/对抗/回归）、评分器、CI 门禁脚本 | **已实现**（`verify.sh` 5/5 通过，有 key 与无 key 双路径均验证） | 6–8 小时 |
| Lab-06 | vLLM 私有化 + 量化 + 语义缓存 | 第 10、17 章 | vLLM 服务 + 量化模型 + 语义缓存层 + 压测脚本 | **已实现**（CPU/无 key 路径可跑；GPU、真实模型与性能阈值按 README 条件复核） | 8–10 小时（GPU）/ 更长（CPU 降级） |
| Lab-07 | 自包含离线部署包 | 第 10 章、上册第 19 章 | 镜像 tar、Helm Chart、双格式 SBOM、cosign 离线签名 + 本地信任根 + 断网安装脚本 | **已实现**（`verify.sh` 7/7；`unshare -rn` 断网验签通过、篡改必被拒、服务以 `--network none` 起） | 6–8 小时 |
| Lab-08 | 可观测性、日志脱敏与成本看板 | 第 10 章 | 真实 Langfuse SDK v4 埋点 + 本地 mock 摄取端 + 脱敏中间件 + 成本归因看板。**摄取端为 mock 而非自托管 Langfuse**（自托管需 4 vCPU/16GiB，写作环境达不到；埋点代码与上报字节均为真） | **已实现**（`verify.sh` 7/7 双路径；PII 零泄漏且业务字段零误伤） | 4–6 小时 |
| Lab-09 | 国产栈演练 | 第 12、13 章 | 五步判据选型（含许可证一票否决）+ CPU 路径实测 + 显存预算表 + 昇腾说明 | **已实现**（`verify.sh` 7/7；CPU 路径实测跑通，昇腾路径如实标注未实测且标注未被滥用） | 6–8 小时（昇腾路径仅文档说明，未实测） |
| Lab-10 | 事件流后台对账智能体 | 上册第 20 章 | Kafka（KRaft）事件流 + 对账 Agent（隔离/归因/起草）+ 补偿 SQL 真执行验证 | **已实现**（`verify.sh` 7/7 双路径；3 条注入全检出、44 条零误报、补偿执行后账平、人工闸门未被越过） | 6–8 小时 |
| Lab-11 | 工作流发现演练 | 上册第 10、11 章 | 虚构客户材料包 + Scoping 文档模板 + 参考答案 | **已实现**（`verify.sh --example` 11/11 通过，退出码 0） | 3–4 小时（纯文档演练） |
| Lab-12 | 毕业项目 | 上册第 9 章、别册三第 1 章 | 完整客户场景包（3 场访谈 + 数据样本 + 分阶段任务书）+ 六道关卡端到端参考实现 + 自评量表 | **已实现**（`verify.sh` 7/7；量表覆盖六道关卡 15 条通过标准，且能判掉“应该没问题”式的残缺提交） | 20 小时以上（多日型毕业项目） |

**“归属章”一栏不写册名的都指下册**，跨册的已显式标出“上册”。

“预计耗时”是按 13 周学习计划的节奏估算给读者安排进度用的，不是统一硬件上的计时基准；实际耗时会随环境、模型下载条件和熟练度浮动。

各 Lab 的核心验收标准如下，完整命令与环境限定以对应 README 为准：

- **Lab-01**：给定 10 个样例 PDF（含 3 个故意破损），≥8 个成功输出合规结构，破损件全部进隔离队列，不污染下游。
- **Lab-02**：无证书请求被拒；有效凭据可穿透调用；证书轮换过程中零失败请求。
- **Lab-03**：MCP client 能发现并正确调用全部工具；注入故障时降级路径生效，不崩溃；不可逆工具（审批）在诱导性表述下零误触发。
- **Lab-04**：在给定评测集上，混合检索的 Recall@5 显著优于纯向量基线，脚本自动对比并打印两者数值。
- **Lab-06**：压测报告显示 P95 延迟达标；缓存命中率与错误命中率同时打印；无 GPU 环境降级为 CPU 小模型时，验收阈值相应放宽并在 README 说明放宽了多少、为什么。
- **Lab-07**：在断网容器中执行离线安装脚本能成功起服务；SBOM 与签名校验通过。
- **Lab-08**：一次完整调用在 Langfuse 中可见完整 trace；PII 字段在日志中已掩码；成本看板显示每次调用成本。
- **Lab-09**：CPU 路径必须实测跑通；昇腾路径若无硬件，README 明确标注为“基于官方文档的流程说明，未实测”，不假装已验证。
- **Lab-10**：注入一条不一致记录，Agent 能隔离、诊断根因、输出可执行的补偿 SQL，脚本校验 SQL 语法有效且逻辑正确。
- **Lab-12**：参考实现能跑通完整闭环；自评量表覆盖六道关卡全部通过标准。

Lab-05 和 Lab-11 的验收标准同样列在这里，方便理解“跑通”具体指什么：

- **Lab-05**：故意引入一个劣化改动（护栏被关闭 + 检索结果被注入噪声 + 一个历史故障被重新引入），CI 门禁必须阻断；恢复后必须放行。
- **Lab-11**：这是文档型 Lab，`verify.sh` 只检查学员产出的 Scoping 文档是否包含全部必填段落与至少一条量化验收指标，不检查判断是否正确——真正的自评要靠 `reference-answer.md`。

## A.2 依赖关系图

12 个 Lab 不是互相独立的练习，其中几组存在明确的前置关系——这些关系分两类：一类是实施计划正文里已经写明的技术依赖（下图用实线标出），另一类是本附录基于 Lab 产出物的技术逻辑做出的建议顺序（下图用虚线标出，属于工程判断而非计划原文明示，读者可以按自己节奏调整）。

```{=latex}
\fdfig{\fdlabgraph}
```

图里几条实线依赖是能在实施计划正文里直接找到依据的：

- **Lab-05 → Lab-06**：第 10 章 §10.6 明确写道“压测输入应该用黄金集覆盖典型场景、对抗集覆盖边缘和高负载场景……这是本书 Lab-06 的验收标准之一”——Lab-06 的压测数据集不是另起一套，直接复用 Lab-05 产出的三层评估集。
- **Lab-04 → Lab-06**：第 17 章（案例四 · 高并发 RAG 性能手术）的任务描述是“全链路优化：混合检索 + RRF 提精度、私有化替换商业 API、量化与 vLLM、语义缓存”，顺序上先靠 Lab-04 的检索链路把精度提上去，再用 Lab-06 的服务化和缓存手段把延迟压下来——两者在同一个案例里被同时引用，且有明确的先后逻辑。
- **Lab-01 → Lab-10**：上册第 20 章（混乱数据摄取与自主对账）同时关联这两个 Lab，Lab-01 摄取并结构化的脏数据，是 Lab-10 对账 Agent 处理事件流时要比对的基础数据。

虚线部分（Lab-02→Lab-03、Lab-06→Lab-07→Lab-08、Lab-11 对 Lab-01/Lab-05 的方法论支撑、以及 Lab-12 对多个前置 Lab 的综合依赖）是本附录基于产出物性质做的合理推断，实施计划里没有逐条写明先后顺序，读者按自己的学习路径调整不影响使用。Lab-09（国产栈演练）在图里没有画依赖线，它是相对独立的横向练习，跟第 12、13 章的国产化适配内容绑定，不依赖其他 Lab 的产出。

## A.3 环境准备

### 有 GPU：标准路径

如果本地或云端有可用 GPU，走标准路径：Docker + NVIDIA Container Toolkit + vLLM 官方 GPU 镜像。Lab-06、Lab-09 的验收阈值按 README 里“标准档”执行，不需要放宽。模型可以用开源权重直接跑量化前的原始精度做对比基线，压测数字更能反映真实生产场景的延迟表现。这条路径本书没有实测环境可用，具体镜像版本与驱动匹配关系以 vLLM 官方文档当时的版本为准，不在本附录里给出可能过时的具体版本号。

### 无 GPU（本书实测环境）：Docker + Ollama + 小模型，或走云端 API

本书写作与验证 Lab 骨架时用的实际环境没有 GPU（`nvidia-smi` 不存在），2 核 CPU，3G 内存左右，这个配置代表相当一部分读者的真实处境——不是每个人都能随手拿到一张卡。实测环境的关键事实：

| 项 | 实测结果 |
|---|---|
| Docker | 29.5.2 |
| Docker Compose | v5.1.4 |
| 本地降级模型 | Ollama + `qwen2.5:0.5b`（397MB，CPU 可跑） |
| 本地模型端点 | `http://127.0.0.1:11434/v1`（OpenAI 兼容） |

**模型接入必须走双路径，不能只写一条。** 有真实 API key（本书用的是 DeepSeek）时走云端 API，验证效果达标；没有 key 时自动降级到本地小模型，验证机制正确——这不是权宜之计，是刻意的设计要求，因为买这本书的读者不会拿到作者的 key。判断逻辑很直接：

```python
import os
if os.getenv("DEEPSEEK_API_KEY"):
    base_url, model = os.getenv("DEEPSEEK_BASE_URL"), "deepseek-chat"
    api_key = os.environ["DEEPSEEK_API_KEY"]
else:
    base_url, model, api_key = "http://127.0.0.1:11434/v1", "qwen2.5:0.5b", "ollama"
```

**验收标准分两档**：有 key 时验“效果达标”（比如 Lab-04 的 Recall@5 数值、Lab-05 的 LLM-as-Judge 打分质量）；没有 key 时验“机制正确”（比如 Lab-05 的门禁能不能正确识别劣化并阻断，即便打分的绝对数值因为用了小模型而偏低）。这个两档设计本身就是第 10 章讲的三档降级方案的实践——Lab 自己就是那一章的活教材。

**key 只从环境变量读，禁止写进任何提交的文件**——`.env` 已经加入 `.gitignore`，代码里只允许 `os.getenv`，不允许出现任何硬编码的 key 字符串，这条红线适用于全部 12 个 Lab，没有例外。

**两条路径都不满足怎么办**——既没有 GPU、也没有任何云端 API key、本地又没装 Ollama，这种情况下大部分 Lab 确实跑不起来，这不是本书回避的问题：Lab-11（工作流发现）和 Lab-12 的自评量表环节不依赖模型调用，可以先做；其余 Lab 至少要先装好 Ollama 并拉取 `qwen2.5:0.5b`——397MB 的下载量和纯 CPU 推理，是这套双路径设计里对硬件要求最低的一档，装好之后再回来跑 A.4 的检查脚本确认环境就绪。

昇腾等国产算力路径是 Lab-09 的一部分，本书写作环境里没有对应硬件，Lab-09 的 README 会明确把这部分标注为“基于官方文档的流程说明，未实测”——这和“无 GPU 走 CPU 降级”是两个不同性质的缺口：CPU 降级路径本书能实测跑通，昇腾路径本书没有硬件条件去验证，两者在验收标准里必须分开表述，不能因为都属于“非标准路径”就用同一句话含糊带过。

## A.4 一键环境检查脚本

下面这段脚本检查 Python 版本、Docker、Ollama、磁盘空间、内存和 CPU 核数，每一项打印 `[PASS]` / `[WARN]` / `[FAIL]`，硬性缺失项（Python 版本不够、Docker 不可用）返回退出码 1，非硬性项（没有 GPU、内存偏低）只警告不阻断。这段脚本本身已经在本书实测环境跑过，不是纸面设计：

```bash
#!/usr/bin/env bash
# check-lab-env.sh —— 12 个 Lab 的通用环境自检脚本
set -uo pipefail

PASS=0; FAIL=0; WARN=0
pass() { printf "  [PASS] %s\n" "$1"; PASS=$((PASS+1)); }
fail() { printf "  [FAIL] %s\n" "$1"; FAIL=$((FAIL+1)); }
warn() { printf "  [WARN] %s\n" "$1"; WARN=$((WARN+1)); }

echo "=== 1. Python 版本（要求 >= 3.10）==="
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')
    PY_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
    [ "$PY_MINOR" -ge 10 ] && pass "python3 $PY_VER" || fail "python3 $PY_VER 低于 3.10"
else
    fail "未找到 python3"
fi

echo "=== 2. Docker ==="
if command -v docker >/dev/null 2>&1; then
    pass "已安装：$(docker --version)"
    docker info >/dev/null 2>&1 && pass "Docker daemon 可访问" || fail "daemon 无法访问"
else
    fail "未找到 docker（需容器的 Lab：01/03/04/05/06/08/10 无法运行）"
fi

echo "=== 3. Docker Compose ==="
docker compose version >/dev/null 2>&1 && pass "$(docker compose version)" || fail "未找到 docker compose"

echo "=== 4. Ollama（无 GPU/无 API key 时的降级路径）==="
if command -v ollama >/dev/null 2>&1; then
    pass "已安装：$(ollama --version 2>&1)"
    if curl -s -m 3 http://127.0.0.1:11434/v1/models >/dev/null 2>&1; then
        pass "Ollama 服务已在 127.0.0.1:11434 监听"
        ollama list 2>/dev/null | grep -q "qwen2.5:0.5b" \
            && pass "模型 qwen2.5:0.5b 已拉取" \
            || warn "未找到 qwen2.5:0.5b，需要执行：ollama pull qwen2.5:0.5b"
    else
        warn "Ollama 已安装但服务未监听，需要执行：ollama serve"
    fi
else
    warn "未找到 ollama——如果也没有 DEEPSEEK_API_KEY，Lab 将无法运行"
fi

echo "=== 5. GPU（非硬性要求，仅提示走哪条路径）==="
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    pass "检测到 nvidia-smi，可走 GPU 标准路径"
else
    warn "未检测到 GPU，Lab-06/09 走 CPU 降级路径，验收阈值按 README 放宽档执行"
fi

echo "=== 6. 磁盘空间（建议根分区可用 >= 10G）==="
AVAIL_G=$(( $(df -Pk / | awk 'NR==2 {print $4}') / 1024 / 1024 ))
[ "$AVAIL_G" -ge 10 ] && pass "根分区可用 ${AVAIL_G}G" || warn "根分区可用仅 ${AVAIL_G}G"

echo "=== 7. 内存（建议总量 >= 4G，可用 >= 1G）==="
TOTAL_MEM_MB=$(free -m | awk '/^Mem:/ {print $2}')
AVAIL_MEM_MB=$(free -m | awk '/^Mem:/ {print $7}')
[ "$TOTAL_MEM_MB" -ge 4000 ] && pass "总内存 ${TOTAL_MEM_MB}MB" || warn "总内存仅 ${TOTAL_MEM_MB}MB，需容器的 Lab 建议串行跑"
[ "$AVAIL_MEM_MB" -ge 1000 ] && pass "当前可用内存 ${AVAIL_MEM_MB}MB" || warn "当前可用内存仅 ${AVAIL_MEM_MB}MB"

echo "=== 8. CPU 核数 ==="
NCPU=$(nproc)
[ "$NCPU" -ge 4 ] && pass "CPU 核数 $NCPU" || warn "CPU 核数仅 $NCPU，多容器并行会吃力"

echo
echo "=== 汇总：$PASS 项通过 / $WARN 项警告 / $FAIL 项失败 ==="
[ "$FAIL" -gt 0 ] && { echo "存在硬性缺失项，按上方 [FAIL] 提示先解决。"; exit 1; }
echo "硬性项全部通过，[WARN] 项不阻塞，但会影响并行度或走哪条降级路径。"
exit 0
```

在本书实测环境（2 核 CPU、约 3.9G 内存、无 GPU）跑这段脚本，实际输出如下：

```
=== 1. Python 版本（要求 >= 3.10）===
  [PASS] python3 3.12.3
=== 2. Docker ===
  [PASS] 已安装：Docker version 29.5.2, build 79eb04c
  [PASS] Docker daemon 可访问
=== 3. Docker Compose ===
  [PASS] Docker Compose version v5.1.4
=== 4. Ollama（无 GPU/无 API key 时的降级路径）===
  [PASS] 已安装：ollama version is 0.32.6
  [PASS] Ollama 服务已在 127.0.0.1:11434 监听
  [PASS] 模型 qwen2.5:0.5b 已拉取
=== 5. GPU（非硬性要求，仅提示走哪条路径）===
  [WARN] 未检测到 GPU，Lab-06/09 走 CPU 降级路径，验收阈值按 README 放宽档执行
=== 6. 磁盘空间（建议根分区可用 >= 10G）===
  [PASS] 根分区可用 12G
=== 7. 内存（建议总量 >= 4G，可用 >= 1G）===
  [WARN] 总内存仅 3915MB，低于 4G，需容器的 Lab 建议串行跑、不要并行
  [PASS] 当前可用内存 1546MB
=== 8. CPU 核数 ===
  [WARN] CPU 核数仅 2，多容器并行会吃力，建议阶段四式的串行/2 个并行策略

=== 汇总：9 项通过 / 3 项警告 / 0 项失败 ===
硬性项全部通过，[WARN] 项不阻塞，但会影响并行度或走哪条降级路径。
```

这份输出印证了实施计划里“阶段四不能像阶段三那样 6 个并行”的判断——3 项警告都指向同一个结论：CPU 核数和内存都吃紧，需容器的 Lab（01/03/04/05/06/08/10）应该串行跑或最多两个并行，纯文档型 Lab（11/12）不占容器资源，可以随时穿插进行。读者在自己的机器上跑这段脚本，如果 [FAIL] 项为 0，就具备了跑全部 12 个 Lab 的基础环境条件。

每个 Lab 目录下有自己的 `verify.sh` 做该 Lab 特定的验收检查，本节这段脚本只负责环境层面的通用前提，不替代任何单个 Lab 的验收脚本。

环境准备好之后，下一步是照着检查清单走完一个真实项目的关键节点：工程执行侧的三张（上线、交接、事故响应的工程细化版）在**本册附录 B**；决策与商务侧的几张（Scoping、安全合规、离场边界、死法自查、五层自查）在**上册附录 B**。清单里引用的方法论（可行性三角、验收标准写法、灰度策略、故障演练判据）都是本书正文已经讲透的内容，附录只做摘录整理，不重复展开论证过程。
