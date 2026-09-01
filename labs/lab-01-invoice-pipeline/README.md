# Lab-01 · 脏 PDF 发票摄取管道

服务《前线部署工程师（FDE）：把 AI 交付到真实世界》下册第 5 章 §5.1（结构化抽取：模型抽取 → 强类型校验 →
自纠错回灌 → 隔离队列）。本 Lab 把这套机制做成一条能真跑通的最小管道，处理
10 份现场风格的"脏"发票 PDF（7 份可解析但格式各异，3 份结构性破损）。

## 目标

1. 从一批版式各异、编码各异、金额正负号各异的 PDF 发票里，稳定抽出
   `invoice_no` / `invoice_date` / `amount_excl_tax` / `tax_amount` / `total`
   五个字段。
2. 用 Pydantic 强类型校验层挡住两类坏结果：**格式不合规**（日期解析不出来、
   金额不自洽）和**看似合规但凭空编造**（模型编一个格式正确但原文里根本
   不存在的发票号/金额——这是本 Lab 重点防的）。
3. 校验失败时，把错误信息**回灌进下一轮 prompt**强制模型自纠正，多轮仍
   失败才进隔离队列，不让半份/编造的数据流入下游。
4. 破损文件（截断、无文本层扫描件）在**调用模型之前**就被确定性规则拦下，
   不浪费一次模型调用，也不给模型编造的机会。

## 目录结构

```
lab-01-invoice-pipeline/
├── README.md
├── verify.sh                     一键验收脚本（判定逻辑不可改）
├── fixtures/
│   ├── generate.py               生成 10 份 PDF 夹具 + manifest.json
│   ├── pdfs/                     10 份发票 PDF（7 脏可解析 + 3 破损）
│   └── expected/manifest.json    每份夹具的期望结果（outcome/expect/dirt）
└── src/
    ├── textutil.py                字符归一化：NFKC + 连字符收敛
    ├── pdf_text.py                PDF 文本抽取（pdftotext 主 + fitz 兜底）
    ├── rules.py                   确定性规则：空文本准入门槛 + 正则草稿抽取
    ├── schema.py                  Pydantic 强类型校验层 + 反编造 grounding 校验
    ├── llm_client.py              双路径 LLM 客户端（DeepSeek / Ollama 降级）
    ├── extractor.py               模型抽取 + 自纠错回灌循环
    ├── run_pipeline.py            管道入口
    └── check_results.py           验收打分辅助（verify.sh 调用）
```

## 前置条件

- Python 3.12（3.10+ 应该都可以）；`pip install pydantic openai python-dotenv`
  （本机已装，`pydantic` 是本 Lab 新增依赖）
- `pdftotext`（`poppler-utils`）在 PATH 里；`PyMuPDF`（`fitz`）已装，作为兜底解析器
- 仓库根目录 `.env` 里有 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`（可选，见下方降级说明）
- 无 key 时需要本机 Ollama 跑起来并已拉取 `qwen2.5:0.5b`：
  ```bash
  ollama pull qwen2.5:0.5b
  ```

**Key 只从环境变量读取，本 Lab 任何文件都不写入真实 key。**

## 双路径（硬要求，不可替换的部分）

`src/llm_client.py` 里写死了这段逻辑：

```python
if os.getenv("DEEPSEEK_API_KEY"):
    base_url, model, key = os.getenv("DEEPSEEK_BASE_URL"), "deepseek-chat", os.environ["DEEPSEEK_API_KEY"]
else:
    base_url, model, key = "http://127.0.0.1:11434/v1", "qwen2.5:0.5b", "ollama"
```

## 步骤

```bash
cd labs/lab-01-invoice-pipeline
# 有 key（在仓库根目录 .env 里配好 DEEPSEEK_API_KEY 即可，脚本不读 .env，
# 需要先 export 到 shell）：
set -a && source ../../.env && set +a
bash verify.sh

# 无 key（验证降级路径）：
DEEPSEEK_API_KEY= bash verify.sh
```

`verify.sh` 跑 6 项检查，全部 OK 且以 exit code 0 结束才算通过。也可以只单独跑管道看产出：

```bash
python3 -m src.run_pipeline --input fixtures/pdfs --out results
python3 -m src.check_results --out results --manifest fixtures/expected/manifest.json --mode classify
```

## 管道设计：确定性规则 vs 模型，各管哪一段

本 Lab 刻意把判断拆成三层，而不是"一股脑丢给模型"：

| 层 | 谁负责 | 处理什么 |
|---|---|---|
| **准入门槛** | 确定性规则（`rules.py::empty_text_reason`） | 文本抽取为空/过短（截断文件、无文本层扫描件）→ **直接隔离，不调用模型**。不该让模型对着空字符串去"编"一份发票。 |
| **抽取** | 模型（`extractor.py`） | 有文本层的 7 份"脏但可解析"发票 + 1 份"文本齐全但缺关键字段"的坏件——版式、字段顺序、日期格式、全角字符这些"表层脏"交给模型处理，这正是模型比正则更擅长的部分。正则草稿（见下）会作为 prompt 里的提示，帮弱模型少走弯路，但最终输出必须是模型自己给的、并独立过校验。 |
| **校验 + 反编造** | 强类型校验层（`schema.py`） | Pydantic 格式/自洽校验（日期能不能解析、`amount_excl_tax + tax_amount == total`）+ **grounding 校验**：字段值必须能在原文里找到字面依据，格式正确但原文不存在的值一律打回。这是防模型"一本正经编发票号"的最后一道闸。 |
| **兜底** | 确定性规则草稿（`rules.py::parse_draft`） | 模型自纠错 `MAX_ATTEMPTS`（3）轮仍不合规时，管道会再单独校验一次纯正则抽出的草稿——草稿本身也必须独立通过同一套 Pydantic + grounding 校验才会被采用（标记 `source: "rule_fallback"`），不是"随便凑合"。草稿本来就抽不全（比如 bad-10 缺发票号/金额）时，这条路也走不通，照样隔离。 |

这个分层直接对应任务书里的提示："如果 0.5B 实在做不到归类，说明管道过度依赖模型，该用确定性规则先做一层筛"——本 Lab 把"先做一层筛"落在两端（准入门槛 + 兜底），中间的抽取仍然真实经过模型，保证 [6/6] 的自纠错证据不是假的。

每份文件的完整处理记录（状态、字段值、每一轮模型输出与校验错误）落在
`results/records/<文件名>.json`；每一次"回灌重试"事件追加写到
`results/retries.jsonl`。

## 验收标准：有 key / 无 key 两档

| 检查项 | 无 `DEEPSEEK_API_KEY`（降级到 `qwen2.5:0.5b`） | 有 `DEEPSEEK_API_KEY`（`deepseek-chat`） |
|---|---|---|
| [1/6] 夹具完整性 | 必须通过，标准不变 | 必须通过，标准不变 |
| [2/6] 管道可运行 | 必须通过，标准不变 | 必须通过，标准不变 |
| [3/6] 归类正确率 ≥8/10 | **标准不变**——考的是管道逻辑（准入门槛 + 校验 + 兜底），不是模型能力 | 标准不变 |
| [4/6] 破损件隔离 3/3 | **标准不变**——3 份破损件在调用模型之前就被规则拦下，与模型能力无关 | 标准不变 |
| [5/6] 字段抽取 | **降级为 schema 校验**：只要求输出符合 Pydantic schema，不要求字段值与 manifest 完全一致（`qwen2.5:0.5b` 抽不准是预期的） | **严格模式**：7 份 pass 夹具的字段值必须与 `manifest.expect` 完全一致 |
| [6/6] 自纠错循环 ≥1 次 | 必须通过，标准不变——真实触发次数视模型当轮表现浮动（实测 7～11 次不等） | 必须通过，标准不变（实测稳定 2 次，均来自 bad-10） |

也就是说：**归类正确率与破损件隔离这两项，无论有没有 key 都是同一套硬标准**，
因为它们建立在"准入门槛 + 校验层 + 确定性兜底"之上、不依赖模型抽取质量；
唯一随 key 有无变化验收严格度的是字段抽取的准确性要求。

## 常见故障排查

| 现象 | 可能原因 | 排查方法 |
|---|---|---|
| `[3/6]`/`[4/6]` 报归类不足 | 破损文件被误判为可解析，或反过来 | 单独看 `results/records/<文件>.json` 的 `status`/`reason`；先确认 `pdftotext -layout <文件> -` 的原始输出是否真的为空/报错 |
| `[5/6]`（有 key）字段值总差一点 | 日期/金额格式没被正确归一化 | 检查是否漏做 NFKC（全角字符）或连字符收敛（本 Lab 用 NotoSerifCJK 字体渲染 ASCII 连字符时，`pdftotext` 抽出来的往往是 U+2011 而不是 U+002D，`textutil.normalize()` 里专门处理了这个） |
| `[6/6]` 报 0 次重试 | `MAX_ATTEMPTS` 被改成 1，或校验层被放水导致模型首轮就"过了" | 检查 `run_pipeline.py::MAX_ATTEMPTS`；不要为了让检查项好看而人为调低校验严格度或强行制造一次失败——夹具本身天然会触发 |
| `ModuleNotFoundError: pydantic` | 依赖没装 | `pip install pydantic`（如遇 externally-managed-environment 报错，用当前环境已验证可行的方式安装，不要改动全局 Python） |
| 无 key 时报 `Connection refused` | 本机 Ollama 没起 | `ollama serve` 起服务，`ollama pull qwen2.5:0.5b`，`curl http://127.0.0.1:11434/api/tags` 确认可达 |
| 无 key 时偶尔归类比 10/10 低 | `qwen2.5:0.5b` 输出不稳定 | 正常现象的极端情况；`rule_fallback` 机制已覆盖大部分场景，若持续失败可把 `MAX_ATTEMPTS` 调大（默认 3），或检查 `rules.py::parse_draft` 是否对新夹具生效 |

## 可替换项（换组件时改哪里）

- **换 PDF 解析器**（比如换 `pdfplumber`，或接入真 OCR 处理扫描件）：只改
  `src/pdf_text.py`，保持 `extract_text(path) -> (text, error)` 签名不变。
- **换校验框架**（比如从 Pydantic 换成 `jsonschema` 手写校验）：只改
  `src/schema.py`，保持 `InvoiceExtraction` 的字段集合、`check_grounding()`
  的语义、异常信息"人类可读、可直接回灌"这三点不变。
- **换 LLM 提供方**：只改 `src/llm_client.py` 的 `get_client_config()`，
  双路径判定逻辑本身是任务书硬要求，不要动。
- **换发票模板/字段集合**：`rules.py` 里的标签词表（`_EXCL_LABELS` 等）和
  `schema.py` 里的 `invoice_no` 正则都是针对这批夹具写的"笨"规则，换一批
  真实客户的发票模板大概率需要重新调整或干脆放弃正则草稿、完全依赖模型。

## 延伸练习

1. **把反编造 grounding 校验做成可配置的容忍度**：现在是"数值必须原文字面
   命中"，试试改成"编辑距离 ≤ N"或"允许模型做单位换算后的等价数值"，
   观察漏检（真编造但过了）和误伤（真实但格式差异大被打回）的权衡。
2. **加一个真实 OCR 环节**：`bad-09-scanned-no-text.pdf` 现在直接被规则隔离；
   接入 `pytesseract` 或云 OCR，看能不能把这类扫描件也纳入可抽取范围，
   同时想清楚 OCR 识别错误要不要也过同一套校验层。
3. **把 `rule_fallback` 的兜底策略做成可观测指标**：跑几次无 key 路径，
   统计"纯模型成功 / 规则兜底成功 / 隔离"三者的比例随 `qwen2.5:0.5b`
   输出波动的变化，量化"管道对模型能力的依赖程度"。
4. **给隔离队列加人工复核出口**：现在隔离就是终点；设计一个
   `results/quarantine_review.jsonl` 或类似的复核队列格式，让人工可以
   补录缺失字段后重新灌回下游，而不是简单丢弃。
5. **把 `MAX_ATTEMPTS` 和校验容差做成实验参数**：分别调整重试轮数
   （1～5）和金额自洽容差，画出无 key 路径下归类正确率的曲线，找到
   "多给模型几次机会"边际收益开始下降的拐点。

## 与下册第 5 章的对应关系

| 下册第 5 章位置 | 本 Lab 对应实现 |
|---|---|
| 11.1 结构化抽取四段式（模型抽取 → 强类型校验 → 自纠错回灌 → 隔离队列） | `src/extractor.py::extract_with_self_correction` + `src/schema.py` |
| "校验层不能只查格式，还要防编造" | `src/schema.py::check_grounding`；无 key 路径下 `qwen2.5:0.5b` 在 `bad-10` 上真实编造过发票号，被此机制当场拦下（见 `results/records/bad-10-missing-critical.json` 的 `attempts`） |
| "不要让模型处理它不该处理的输入" | `src/rules.py::empty_text_reason`：截断文件/扫描件在调用模型之前就被拦下 |
