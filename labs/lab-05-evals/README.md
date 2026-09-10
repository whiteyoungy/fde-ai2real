# Lab-05：企业 Evals 框架 + 红队集 + CI 门禁

服务《前线部署工程师（FDE）：把 AI 交付到真实世界》下册第 10 章《评估的工程实现》。本 Lab 把下册第 10 章讲的**三层评估集结构**
（黄金集 / 对抗集 / 回归集）、**确定性评分器 + LLM-as-Judge**、**CI 发布门禁**做成一套
真跑通的最小实现，用来验证下册第 10 章正文里标了 `<!-- UNVERIFIED: Lab-05 -->` 的代码块。

## 目标

1. 三层评估集（`datasets/golden.jsonl` / `adversarial.jsonl` / `regression.jsonl`）能被
   加载、校验并跑通评分。
2. 评分器同时提供「确定性评分」（精确匹配 / 包含 / 正则 / JSON Schema 校验）与
   「LLM-as-Judge」（含至少一种偏差缓解手段：本 Lab 实现**成对比较 + 顺序打乱**）。
3. `src/gate.py` 读评估结果，按第 7.6 节的判定表给出放行/阻断决定，并给出明确失败原因。
4. **核心验收**：故意引入一个劣化（系统提示词/护栏被关闭 + 检索结果被注入噪声 +
   一个历史故障被重新引入），门禁必须阻断；恢复后必须放行。这比"脚本能跑完"高一个量级——
   门禁要证明自己真的能拦住真实劣化。

## 目录结构

```
lab-05-evals/
├── README.md
├── requirements.txt
├── verify.sh                     # 一键验收脚本（TDD 第一步就写好，此时必然失败）
├── configs/
│   ├── system_baseline.yaml      # 基线系统配置：护栏开启，无检索噪声
│   ├── system_degraded.yaml      # 劣化系统配置：护栏关闭 + 检索噪声 + 重引入历史故障
│   └── thresholds.yaml           # CI 门禁阈值（对齐第 7.6 节判定表）
├── datasets/
│   ├── kb.jsonl                  # 被测系统的知识库（支撑素材，非三层集合之一）
│   ├── golden.jsonl              # 黄金集：业务真值，24 条
│   ├── adversarial.jsonl         # 对抗集：prompt injection / 越狱 / OWASP LLM Top10，12 条
│   └── regression.jsonl          # 回归集：历史故障固化，8 条
├── src/
│   ├── llm_client.py             # 双路径 LLM 客户端（DeepSeek / Ollama 降级）
│   ├── sut.py                    # 被测系统（Mock RAG）：检索 + 生成 + 护栏
│   ├── scorers.py                # 确定性评分器 + LLM-as-Judge（成对比较/顺序打乱）
│   ├── run_eval.py                # 评估运行器：跑三层集合，输出 JSON + 人类可读摘要
│   └── gate.py                    # CI 门禁：读结果，按阈值判定放行/阻断
└── .github/workflows/evals.yml   # CI 门禁配置（配置文件即可，无需真在 GitHub 跑）
```

## 前置条件

- Python 3.12（已验证；3.10+ 应该都可以）
- `pip install -r requirements.txt`（`openai` / `python-dotenv` / `PyYAML` / `jsonschema`，
  均为常见包，本机已安装）
- 仓库根目录 `.env` 里有 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`（可选，见下方降级说明）
- 无 key 时需要本机 Ollama 跑起来并已拉取 `qwen2.5:0.5b`：
  ```bash
  ollama pull qwen2.5:0.5b
  ```

**Key 只从环境变量读取（`python-dotenv` 从仓库根 `.env` 加载），本 Lab 任何文件都不写入
真实 key。**

## 双路径（硬要求，不可替换的部分）

`src/llm_client.py` 里写死了这段逻辑，任何调用 LLM 的地方都必须经过它：

```python
if os.getenv("DEEPSEEK_API_KEY"):
    base_url, model, api_key = os.getenv("DEEPSEEK_BASE_URL"), "deepseek-chat", os.environ["DEEPSEEK_API_KEY"]
else:
    base_url, model, api_key = "http://127.0.0.1:11434/v1", "qwen2.5:0.5b", "ollama"
```

## 步骤

```bash
cd labs/lab-05-evals
pip install -r requirements.txt
./verify.sh
```

`verify.sh` 跑 5 项检查，每项打印一行人类可读结果，全部 OK 且脚本以 exit code 0 结束才算通过。

## 关键设计：为什么门禁测试不依赖真实 LLM 生成

`src/sut.py` 里的"被测系统"是一个**确定性的 Mock RAG**：关键词检索 + 模板拼接生成，
不调用任何 LLM。这是有意为之，原因直接对应任务里"无 key 也必须能完整跑通验收"的硬要求：

- 门禁有效性测试（verify.sh 第 5 项）如果依赖 `qwen2.5:0.5b` 这种极弱模型生成答案，
  基线本身的通过率就可能不稳定（弱模型连基线都答不对），会把"门禁逻辑对不对"和
  "模型生成质量好不好"这两件独立的事情混在一起，导致验收脚本在无 key 环境下变得不可复现。
- 用确定性 Mock SUT，"劣化"就能被精确控制为三个可解释的独立机制：
  1. **护栏开关**（`guardrail_enabled: false`）——对抗集的注入/越狱请求不再被拒绝；
  2. **检索噪声注入**（`retrieval_noise_rate`）——按固定种子的伪随机把部分黄金集查询的
     检索结果替换成不相关 chunk，命中的事实点（`key_facts`）在生成结果里消失；
  3. **历史故障重新引入**（`regression_bugs_reintroduced`）——回归集里某条已修复的
     故障对应的知识库修复条目被从检索候选里移除，故障复现。
- 这三个机制都是通过 `configs/system_degraded.yaml` 声明式配置的，`gate.py`/`scorers.py`
  完全不知道"这是不是劣化跑"——它们只看评分结果，这保证了门禁测试的有效性不是"脚本认识
  degraded 这个词就自动阻断"的假把式。

LLM 的双路径调用被隔离在 **LLM-as-Judge** 评分器（`scorers.py` 里的
`make_llm_faithfulness_judge` / `llm_pairwise_judge`），这部分是本 Lab 里唯一真正调用
DeepSeek/Ollama 的地方，也是验收标准按有无 key 分档的地方（见下）。

## 验收标准：有 key / 无 key 两档

| 检查项 | 无 `DEEPSEEK_API_KEY`（降级到 `qwen2.5:0.5b`） | 有 `DEEPSEEK_API_KEY`（`deepseek-chat`） |
|---|---|---|
| [1/5] 三层评估集加载 | 必须通过，标准不变 | 必须通过，标准不变 |
| [2/5] 确定性评分器 | 必须通过，标准不变（不依赖模型） | 必须通过，标准不变 |
| [3/5] LLM-as-Judge 偏差缓解 | **降级为"跑通即可"**：只验证成对比较调用不抛异常、能解析出一个胜者标签、顺序打乱确实生效（两次调用呈现顺序不同）。不要求胜者判断正确 | **验证判别力**：对一个明显更忠实的答案 vs 一个明显编造事实的答案做成对比较，要求顺序正/反两次都判给忠实答案（一致），验证偏差缓解后判断没有被顺序左右 |
| [4/5] 基线评估 | 必须通过，标准不变（Mock SUT 不受模型能力影响） | 必须通过，标准不变 |
| [5/5] 门禁有效性 | 必须通过，标准不变（Mock SUT 机制，与模型无关） | 必须通过，标准不变 |

也就是说：**三层评估集加载、确定性评分器、基线评估、门禁有效性这四项，无论有没有
key 都是同一套硬标准**——因为它们全部构建在确定性 Mock SUT 之上。唯一随 key 有无变化验收
严格度的，是第 3 项 LLM-as-Judge 的偏差缓解验证。

## 常见故障排查

| 现象 | 可能原因 | 排查方法 |
|---|---|---|
| `[3/5]` 报错 `Connection refused` | 无 key 且本机 Ollama 没起 | `ollama serve` 起服务，`ollama pull qwen2.5:0.5b` 拉模型，`curl http://127.0.0.1:11434/api/tags` 确认可达 |
| `[3/5]` 报错 `404 model not found` | Ollama 起了但没拉这个模型 | `ollama pull qwen2.5:0.5b` |
| `[1/5]` 报数据集条数不够 | `datasets/*.jsonl` 被误改 | 用 `git diff` 检查是否有行被删；三层集合的最小规模：golden≥20、adversarial≥8、regression≥5 |
| `[4/5]` 基线通过率异常低 | `configs/system_baseline.yaml` 被误改成了 degraded 的值 | 对比 `configs/system_baseline.yaml` 与 git 历史版本 |
| `[5/5]` 劣化没有被阻断 | `configs/thresholds.yaml` 阈值被放得太松，或 `gate.py` 的零容忍逻辑被绕过 | 检查 `regression_zero_tolerance: true` 是否还在；单独跑 `python3 -m src.run_eval --config configs/system_degraded.yaml` 看 `regression_pass_rate` 是不是真的 <1.0 |
| `[5/5]` 恢复后没有放行 | 上一步跑完后忘了把结果目录里的临时文件清理，或复用了旧的 degraded 结果文件 | `verify.sh` 每次跑都用独立的输出文件名，检查 `results/` 目录残留文件的时间戳 |
| DeepSeek 调用报 401 | `.env` 里的 key 失效或被截断 | 用最小复现脚本单独测试 key：`python3 -c "..."`（不要把 key 打印出来） |
| `ModuleNotFoundError: openai` | 依赖没装 | `pip install -r requirements.txt` |

## 延伸练习

1. **把 Mock SUT 换成真实 LLM 生成**：让 `sut.py` 在拿到检索结果后，调用
   `llm_client.py` 的双路径客户端做真正的生成，而不是模板拼接。做完后重新跑
   `verify.sh`，观察在 `qwen2.5:0.5b` 上基线通过率会不会下降——这正是正文 7.4 节
   "裁判模型本身也要单独评估"背后的同一类问题：生成模型本身能力不足时，"门禁逻辑对不对"
   和"模型能力够不够"会重新纠缠在一起。
2. **补第二种 LLM-as-Judge 偏差缓解**：本 Lab 只实现了"成对比较 + 顺序打乱"，
   照 7.4 节的 few-shot 锚定示例思路，给 `make_llm_faithfulness_judge` 加锚定样例，
   对比加锚定前后，在同一批人工标注的黄金集子集上算一致率有没有提升。
3. **把 `retrieval_noise_rate` 做成参数化实验**：从 0 到 0.6 每隔 0.1 跑一次评估，
   画出 recall@k 与黄金集通过率的曲线，找 7.6 节说的"阈值标定看拐点"的拐点，
   而不是用本 Lab 里示例性的 0.85/0.90 阈值。
4. **加一层"检索 vs 生成"根因归因**：结合第 3.1 节 Barnett 七类失败点，给每个 fail
   的黄金集用例打上 FP1-FP7 标签（可以用检索命中 + 事实覆盖两个信号做规则判断），
   输出到评估摘要里，而不是只报一个通过率数字。
5. **把 CI 门禁接上真实 GitHub Actions**：`.github/workflows/evals.yml` 目前只是配置文件，
   没有在真实 CI 里跑过；把它接到一个真实仓库，用 PR 触发一次，检查 `pull_request` 事件下
   门禁能不能正确挡住一个刻意提交的劣化 PR。

## 与下册第 10 章的对应关系

| 下册第 10 章位置 | 本 Lab 对应实现 |
|---|---|
| 7.2 三层评估集结构（表格） | `datasets/golden.jsonl` / `adversarial.jsonl` / `regression.jsonl`，字段设计对齐正文 schema |
| 7.4 LLM-as-Judge 的坑：位置偏差 | `scorers.py::llm_pairwise_judge` 的顺序打乱 + 一致性检查 |
| 7.6 黄金集/对抗集/回归集 schema（YAML/JSONL 示例） | `datasets/*.jsonl` 实际字段与示例保持兼容，补充了评分需要的 `key_facts`/`refusal_patterns` 等字段 |
| 7.6 评分函数（`EvalCase`/`EvalResult`/`score_golden_case`/`score_regression_case`/`score_adversarial_case`/`gate_decision`） | `src/scorers.py` 保留同名类型与函数签名，补上可运行的默认实现 |
| 7.6 CI 门禁配置 | `.github/workflows/evals.yml`，命令对齐 `src/run_eval.py`/`src/gate.py` 实际 CLI |
