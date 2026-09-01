# 附录 D：参考文献汇总

> **为什么两册收的是同一份完整书目**：拆开会让读者在引用编号上来回跳册，
> 也会让某些链接只出现在一册里。这本书的规矩是引用链接一条不删，
> 所以两册各收一份完整的，宁可重复，不要缺失。

## D.0 说明：来源分层原则与审计结论

本书 29 章各自在章末列了“参考来源”小节，本附录做的事情是把全书分散的引文抽取到一处、按 URL 去重、按类型归类、统一编号，方便读者按类别查阅或核实。**去重后不等于全部一手可靠**——本附录严格保留了每条来源在原章节里标注的质量等级，不会因为一条来源被收进“参考文献”这个更正式的位置，就悄悄抹掉它原本“二手转述”“未逐字核对”“抓取失败”这类限定语。看到某条后面跟着括注，说明原作者当时就是这么标注的，请按标注的可信度对待，不要因为它出现在附录里就默认为一手信源。

**分层标准**（与正文遵循同一套标准，详见 `docs/superpowers/plans/style-guide.md` 第 2 节）：

| 层级 | 判定标准 | 本附录的处理方式 |
|---|---|---|
| 一手可验证 | 官方文档、法条原文、官方模型卡、arXiv 论文全文，经直接抓取或下载核对逐字 | 直接列出，无额外括注 |
| 多源交叉印证 | 同一数字在两个独立信源出现且量级吻合，或经媒体交叉确认标题与日期 | 括注“经…交叉确认”或类似说明 |
| 二手转述/未逐字核对 | 内容来自转述、摘要综合，未直接核对原始文本 | 括注“转述”“未逐字核对”“摘要综合”等原文措辞 |
| 抓取失败/存疑 | 原始页面因 403、SSL 失败、需登录等原因未能直接核对，改用代理或交叉验证 | 括注“抓取受限”“存疑”“待二次核实”等原文措辞 |

**审计结论**：两册重构前的 29 章合订稿由 8 篇调研笔记支撑；正文写作前共核对 530 处引文/数字，修正 87 处，另有 10 处降级为存疑，整体失败率 16.4%。方法论笔记失败率最高，达 22%——这份数据本身就是“大规模扩写是伪造引文高发期”这一结论的来源。审计的失真类型分布、修正案例细节，见 `docs/research/CITATION-AUDIT.md`（全量审计总账）。本附录列出的每一条来源，其对应笔记均已通过该审计闸门；正文写作阶段新增的少量引文（多为官方技术文档与法规原文的直接核对），核实方式已随附在各条目的括注里。

**统计口径**：以下按 URL 与标题去重后，全书共提取到 **214 个去重 URL**，另有约 24 条无独立 URL 但在原文中明确列为引用来源的条目（如法规条文的国标号、内部调研笔记路径、经交叉媒体确认但未留存 URL 的口述内容），二者合计构成本附录的 **238 条编号条目**，去重后条目数远超 120 条的下限。41 个 URL 被两章及以上共同引用，已在对应条目的“被引章节”里列全，不重复出条。

**未纳入范围**：各章内部相互引用（如“本书第 14 章”“见 §7.5”“数据取自 `docs/research/03-tech-stack.md`”这类指向本书自身章节或内部调研笔记的交叉引用）不构成独立的外部参考文献，未在本附录单独编号，仍保留在各章正文的脚注与“参考来源”小节里。第 0 章（导读）与别册三第 1 章（90 天上岗计划，原下册第 16 章）为全书内部编排产物，未引入独立于本附录之外的新外部一手资料。

---

## D.1 官方招聘 JD 与公司工程博客

[1] Dev versus Delta: Demystifying engineering roles at Palantir — Palantir 官方博客，<https://blog.palantir.com/dev-versus-delta-demystifying-engineering-roles-at-palantir-ad44c2a6e87>，检索于 2026-08-07（被引：§1、§28）

[2] Forward-deployed Job Titles — a16z 官方博客，<https://a16z.com/forward-deployed-job-titles/>，检索于 2026-08-07（§1）

[3] Forward Deployed Engineer (FDE) - NYC — OpenAI 官方招聘页，<https://openai.com/careers/forward-deployed-engineer-(fde>)-nyc-new-york-city/，检索于 2026-08-07（§1、§27；未披露薪酬区间）

[4] Applied AI Engineer, Enterprise Tech — Anthropic 官方 Greenhouse，<https://job-boards.greenhouse.io/anthropic/jobs/5057647008>，检索于 2026-08-07（§1、§2、§27）

[5] Applied AI Architect, Enterprise Tech — Anthropic 官方 Greenhouse，<https://job-boards.greenhouse.io/anthropic/jobs/5065835008>，检索于 2026-08-07（§1、§27）

[6] Frontier Agent Engineer (Forward Deployed Engineering) — Scale AI 官方 Greenhouse，<https://job-boards.greenhouse.io/scaleai/jobs/4694861005>，检索于 2026-08-07（§1、§27）

[7] Forward Deployed Engineer (FDE) - Public Sector — Databricks 官方 Greenhouse，<https://job-boards.greenhouse.io/databricks/jobs/8611108002>，检索于 2026-08-07（§1、§27）

[8] AI Engineer - FDE (ALL LEVELS) — Databricks 官方 Greenhouse，<https://job-boards.greenhouse.io/databricks/jobs/8546367002>，检索于 2026-08-07（§1）

[9] Palantir Technologies - Forward Deployed AI Engineer — Palantir 官方 Lever 招聘页，<https://jobs.lever.co/palantir/636fc05c-d348-4a06-be51-597cb9e07488>，检索于 2026-08-07（§1、§27）

[10] 解决方案架构师 -马来西亚/中东(A221670) - 智谱·AI — 猎聘，<https://www.liepin.com/job/1978522673.shtml>，检索于 2026-08-07（§1、§27）

[11] 大装置-大模型解决方案架构师 - 商汤科技SenseTime — 猎聘，<https://www.liepin.com/job/1974798939.shtml>，检索于 2026-08-07（§1、§27）

[12] 资深AI大模型应用开发工程师(J11779) - 智联招聘，<https://www.zhaopin.com/jobdetail/CC154054010J40621118506.htm>，检索于 2026-08-07（§1、§27）

[13] Deploying Full Spectrum AI in Days: How AIP Bootcamps Work — Palantir 官方博客，<https://blog.palantir.com/deploying-full-spectrum-ai-in-days-how-aip-bootcamps-work-21829ec8d560>，检索于 2026-08-07（§2、§6）

[14] Two years of vector search at Notion: 10x scale, 1/10th cost — Notion 官方技术博客，<https://www.notion.com/blog/two-years-of-vector-search-at-notion>，检索于 2026-08-07（§19；活跃工作区增长 15x、向量数据库容量扩展 8x、分阶段成本与延迟数字均逐字核对）

[15] Ask Sage Announces Generative AI Army Enterprise Offering at IL5 in Collaboration with Microsoft — Ask Sage 官方新闻稿，2025-06-30，<https://www.asksage.ai/press-release/ask-sage-announces-generative-ai-army-enterprise-offering-at-il5-in-collaboration-with-microsoft/>，检索于 2026-08-07（§14；直接抓取原文，逐字核对）

[16] Varick Agents 官网与招生页 — varickagents.com、learn.varickagents.com，检索于 2026-08-07（§28）

[17] Varick Agents 招聘页面（Ashby）— jobs.ashbyhq.com/Varick-Agents，检索于 2026-08-07（§28）

[237] Palantir Technologies - Deployment Strategist — Palantir 官方 Lever 招聘页，<https://jobs.lever.co/palantir/e0ab8226-b928-4e3a-bf87-08fe7b1ea595>，检索于 2026-08-28（§1、§2、§7；页面自身标注部门为 Echo，职责清单与“What We Require”两条要求均已抓取原文逐字核对。**编号接在全书末尾，是为了不打乱既有条目的编号**）

[238] Palantir 官方 Lever 招聘板全量职位列表 — <https://jobs.lever.co/palantir>，检索于 2026-08-28（§1；2026-08-28 抓取快照，在招 307 条，按部门标签计 Dev 75、Delta 61、Echo 35。**招聘板公开快照，不是公司披露的编制数据，随时间变动，仅用于量级判断**）

---

## D.2 学术论文（arXiv / 会议 / 期刊）

[18] Repenning, N.P. & Sterman, J.D. (2001). “Nobody Ever Gets Credit for Fixing Problems that Never Happened: Creating and Sustaining Process Improvement.” *California Management Review*, 43(4), 64-88. <https://web.mit.edu/nelsonr/www/Repenning=Sterman_CMR_su01_.pdf>，检索于 2026-08-07（§3、§28）

[19] Jabrayilzade, E. et al. “Bus Factor In Practice.” *Proceedings of ICSE 2022 (SEIP track)*. arXiv:2202.01523，检索于 2026-08-07（§3）

[20] Walid Maalej, Yen Dieu Pham, Larissa Chazette. “Tailoring Requirements Engineering for Responsible AI.” arXiv:2302.10816，检索于 2026-08-07（经下载 PDF 逐页核对逐字确认）（§2、§4、§5）

[21] G. Lynn Shostack. “Designing Services That Deliver.” *Harvard Business Review*, Jan–Feb 1984（经下载 PDF 全文核对逐字确认）（§4）

[22] Wil M.P. van der Aalst. “Process Mining: Discovering and Improving Spaghetti and Lasagna Processes.” IEEE 特邀论文，<https://www.vdaalst.com/publications/p615.pdf>，检索于 2026-08-07（经下载全文核对逐字确认）（§4）

[23] Barnett et al. “Seven Failure Points When Engineering a Retrieval Augmented Generation System.” arXiv:2401.05856，检索于 2026-08-07（§7、§12）

[24] IBM 团队. “Optimizing and Evaluating Enterprise Retrieval-Augmented Generation (RAG): A Content Design Perspective.” arXiv:2410.12812，检索于 2026-08-07（§7、§11、§12；注意书中“RAG 的 7 种失败模式”曾误标为 Barnett et al. 原文，实际逐字出自本文对 Barnett 的转述，已在正文更正）

[25] Shahul Es et al. “Ragas: Automated Evaluation of Retrieval Augmented Generation.” arXiv:2309.15217（§7）

[26] “HarmBench.” arXiv:2402.04249（§7）

[27] “Large Language Models are not Fair Evaluators.” arXiv:2305.17926, ACL 2024（§7）

[28] “Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.” arXiv:2306.05685, NeurIPS 2023（§7）

[29] “Explaining Length Bias in LLM-Based Preference Evaluations.” arXiv:2407.01085（§7）

[30] “LLM Evaluators Recognize and Favor Their Own Generations.” arXiv:2404.13076, NeurIPS 2024（§7）

[31] “G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment.” arXiv:2303.16634（§7）

[32] “Overcoming the 'Impracticality' of RAG: Proposing a Real-World Benchmark and Multi-Dimensional Diagnostic Framework.” arXiv:2604.02640（§7）

[33] Gao et al. “Precise Zero-Shot Dense Retrieval without Relevance Labels”（HyDE）. arXiv:2212.10496，检索于 2026-08-07（§12）

[34] Zackary Rackauckas. “RAG-Fusion: a New Take on Retrieval-Augmented Generation.” arXiv:2402.03367，检索于 2026-08-07（§12；单一企业案例研究，非顶会同行评审）

[35] “Higress-RAG: A Holistic Optimization Framework for Enterprise RAG via Dual Hybrid Retrieval, Adaptive Routing, and CRAG.” arXiv:2602.23374，检索于 2026-08-07（§12、§19；效果数字为单一厂商自测，样本领域狭窄，不构成通用基准）

[36] jina-reranker-v3 论文，arXiv:2509.25085，检索于 2026-08-07（§12；注意与 jina-embeddings-v3、Jina Reranker v2 均为不同模型/论文）

[37] NVIDIA 团队 rerank 评测论文，arXiv:2409.07691，检索于 2026-08-07（§12）

[38] “Corrective Retrieval Augmented Generation”（CRAG）. arXiv:2401.15884, EMNLP 2024 Findings，检索于 2026-08-07（§12、§19；效果数字为论文作者自测）

[39] “Open-Source Reproduction and Explainability Analysis of Corrective Retrieval Augmented Generation.” arXiv:2603.16169，检索于 2026-08-07（§12）

[40] Edge et al. “From Local to Global: A Graph RAG Approach to Query-Focused Summarization”（GraphRAG）. arXiv:2404.16130，检索于 2026-08-07（§12）

[41] “Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach.” arXiv:2407.16833，检索于 2026-08-07（§12）

[42] “LaRA: Benchmarking Retrieval-Augmented Generation and Long-Context LLMs.” arXiv:2502.09977，检索于 2026-08-07（§12）

[43] “LongRAG: Enhancing Retrieval-Augmented Generation with Long-context LLMs.” arXiv:2406.15319，检索于 2026-08-07（§12）

[44] “Long Context RAG Performance of Large Language Models.” Databricks Mosaic Research, arXiv:2411.03538，检索于 2026-08-07（§12）

[45] “Inference Scaling for Long-Context Retrieval Augmented Generation.” arXiv:2410.04343，检索于 2026-08-07（§12）

[46] “A Systematic Analysis of Chunking Strategies for Reliable Question Answering.” arXiv:2601.14123, ECIR 2026（检索摘要核实重叠收益与“上下文悬崖”结论，未逐字核对全文）（§11）

[47] Espino, Sundstrom, Frick, Jacobs, Peters. “International business travel: impact on families and travellers.” *Occupational and Environmental Medicine*, 2002, 59(5):309-22（PubMed ID 11983846），检索于 2026-08-07（§28；**职业倦怠一节已从上册第 14 章移入上册第 3 章 §3.6，本条现由该节引用**）

---

## D.3 官方技术文档（框架、协议、云平台）

[48] Qdrant 官方文档，“Hybrid and Multi-Stage Queries.” <https://qdrant.tech/documentation/concepts/hybrid-queries/>，检索于 2026-08-07（§11、§12、§19；`query_points()`/`RrfQuery`/`FusionQuery` 用法逐字核实）

[49] Qdrant 官方文档，“Filtering.” <https://qdrant.tech/documentation/concepts/filtering/>，检索于 2026-08-07（§11）

[50] Qdrant 官方文档，“Search.” <https://qdrant.tech/documentation/search/search/>，检索于 2026-08-07（§11）

[51] qdrant-client GitHub Releases（v1.16.0、v1.19.0 changelog）. <https://github.com/qdrant/qdrant-client/releases>，检索于 2026-08-07（§11；对 v1.19.0 changelog 表述矛盾处做了源码级核实）

[52] Apache Airflow 官方文档，“TaskFlow API 教程.” <https://airflow.apache.org/docs/apache-airflow/stable/tutorial/taskflow.html>，检索于 2026-08-07（§11）

[53] Apache Airflow 官方文档，“Supported Versions.” <https://airflow.apache.org/docs/apache-airflow/stable/installation/supported-versions.html>，检索于 2026-08-07（§11）

[54] PaddleOCR 官方文档，“PP-StructureV3.” <https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-StructureV3/PP-StructureV3.md>，检索于 2026-08-07（§11、§23）

[55] MinerU 官方 README（中文版）. <https://github.com/opendatalab/MinerU/blob/master/README_zh-CN.md>，检索于 2026-08-07（§11、§23；“三路后端”设计核实）

[56] BAAI/bge-large-zh-v1.5 model card. <https://huggingface.co/BAAI/bge-large-zh-v1.5>，检索于 2026-08-07（§11、§23）

[57] Qwen3 Embedding 官方博客. <https://qwenlm.github.io/blog/qwen3-embedding/>，检索于 2026-08-07（§11、§23；逐字抓取核实 MTEB 多语言榜单排名与 Apache 2.0 license）

[58] RAGAS 官方文档，“available_metrics”（Faithfulness / Answer Relevancy / Context Precision / Context Recall）. <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/>，检索于 2026-08-07（§7、§11）

[59] TruLens (TruEra) 官方文档，“RAG Triad”（§7）

[60] DeepEval (confident-ai)，PyPI 版本 4.1.5（§7）

[61] Arize Phoenix 官方文档（§7）

[62] OWASP, “Top 10 for LLM Applications 2025.” <https://genai.owasp.org/llm-top-10/>（§7、§12）

[63] NVIDIA/garak，GitHub README（§7）

[64] microsoft/PyRIT，GitHub README（§7）

[65] Model Context Protocol 官方文档，“Versioning” 与 “Transports”（含 Deprecated 页面）. <https://modelcontextprotocol.io/specification/versioning>，<https://modelcontextprotocol.io/specification/2026-07-28/basic/transports>，检索于 2026-08-07（§12）

[66] `modelcontextprotocol/python-sdk` 官方仓库，README 与 `docs/migration.md`. <https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md>，检索于 2026-08-07（§9、§12、§15；PyPI JSON API 交叉核实 `info.version == "2.0.0"`）

[67] LangGraph 官方 API 参考文档，`StateGraph`/`add_node`/`compile`/`interrupt`/`Command`. <https://reference.langchain.com/python/langgraph/>，检索于 2026-08-07（§12；正文示例为对官方 Multiple-schemas 示例的简化改写，非逐字摘录，Lab 实现前须实测验证）

[68] LangGraph 官方文档，“Interrupts.” <https://docs.langchain.com/oss/python/langgraph/interrupts>，检索于 2026-08-07（§12、§15）

[69] LangGraph v1 迁移指南. <https://docs.langchain.com/oss/python/migrate/langgraph-v1>，检索于 2026-08-07（§9、§12；“All LangChain packages now require Python 3.10 or higher”）

[70] vLLM GitHub Releases，v0.25.0 发布说明（“PagedAttention has been removed”，PR #47361）. <https://github.com/vllm-project/vllm/releases>，检索于 2026-08-07（经 GitHub Releases API 核实）（§13、§19）

[71] “CPU - vLLM”，官方 CPU 后端安装与运行文档. <https://docs.vllm.ai/en/stable/getting_started/installation/cpu.html>，检索于 2026-08-07（§13）

[72] “OpenAI-Compatible Server - vLLM”，`vllm serve` 官方入口文档. <https://docs.vllm.ai/en/stable/serving/online_serving/openai_compatible_server/>，检索于 2026-08-07（§13）

[73] “Engine Arguments - vLLM”，`--max-model-len`/`--gpu-memory-utilization`/`--quantization` 参数说明. <https://docs.vllm.ai/en/stable/configuration/engine_args/>，检索于 2026-08-07（§13）

[74] “Quantization - vLLM”，量化方案与硬件兼容性表格. <https://docs.vllm.ai/en/latest/features/quantization/index.html>，检索于 2026-08-07（§13）

[75] vLLM Tool Calling 官方文档. <https://docs.vllm.ai/en/latest/features/tool_calling/>，检索于 2026-08-07（§23）

[76] Langfuse, “SDK overview.” <https://langfuse.com/docs/observability/sdk/overview>，检索于 2026-08-07（§13）

[77] Langfuse, “Get Started”（装饰器与上下文管理器代码示例出处）. <https://langfuse.com/docs/observability/get-started>，检索于 2026-08-07（§13）

[78] Langfuse, “Self-hosting: Docker Compose.” <https://langfuse.com/self-hosting/docker-compose>，检索于 2026-08-07（§13）

[79] Sigstore, “Cosign Signing Overview”（keyless 默认签名方式说明）. <https://docs.sigstore.dev/cosign/signing/overview/>，检索于 2026-08-07（§13）

[80] Sigstore, “Signing with self-managed keys”（key-based 签名命令）. <https://docs.sigstore.dev/cosign/key_management/signing_with_self-managed_keys/>，检索于 2026-08-07（§13）

[81] Anchore, syft GitHub README 与 SBOM 格式文档. <https://github.com/anchore/syft>，<https://oss.anchore.com/docs/guides/sbom/formats/>，检索于 2026-08-07（§13）

[82] IETF, *RFC 6749: The OAuth 2.0 Authorization Framework*. <https://www.rfc-editor.org/rfc/rfc6749>，检索于 2026-08-07（§10）

[83] IETF, *RFC 7636: Proof Key for Code Exchange by OAuth Public Clients*；*RFC 8628: OAuth 2.0 Device Authorization Grant*. <https://www.rfc-editor.org/rfc/rfc7636>，<https://www.rfc-editor.org/rfc/rfc8628>，检索于 2026-08-07（§10）

[84] IETF OAuth Working Group, *draft-ietf-oauth-v2-1-13*（OAuth 2.1 草案）第 10 节，援引 *RFC 9700: Best Current Practice for OAuth 2.0 Security*. <https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13>，<https://www.rfc-editor.org/rfc/rfc9700>，检索于 2026-08-07（经 r.jina.ai 代理逐字核对正文）（§10；OAuth 2.1 为持续更新的 Internet-Draft，非正式发布的 RFC，具体条款号可能随后续版本调整）

[85] OASIS, *Security Assertion Markup Language (SAML) V2.0 Core*. <https://docs.oasis-open.org/security/saml/v2.0/saml-core-2.0-os.pdf>，检索于 2026-08-07（§10；仅描述其整体结构与常见故障模式，未逐字引用条款原文）

[86] OpenID Foundation, *OpenID Connect Core 1.0*. <https://openid.net/specs/openid-connect-core-1_0.html>，检索于 2026-08-07（§10；仅描述其整体机制，未逐字引用条款原文）

[87] Elasticsearch 官方文档，“Reciprocal rank fusion.” <https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion>，检索于 2026-08-07（§12、§19）

[88] pip 官方文档，“pip download.” <https://pip.pypa.io/en/stable/cli/pip_download/>，检索于 2026-08-07（§9；`curl` 直接抓取原始 HTML 核对参数说明与用法示例）

[89] pip 官方文档，“Configuration.” <https://pip.pypa.io/en/stable/topics/configuration/>，检索于 2026-08-07（§9）

[90] PyPI JSON API（`mcp`、`qdrant-client` 包元数据）. <https://pypi.org/pypi/mcp/json>，<https://pypi.org/pypi/qdrant-client/json>，检索于 2026-08-07（§9；`qdrant-client` 1.16.2 移除 Python 3.9 支持）

[91] Google SRE Book, “SRE pre launch checklist.” <https://sre.google/sre-book/launch-checklist/>，检索于 2026-08-07（§7、§8）

[92] Google SRE Book, “Evolving SRE Engagement Model.” <https://sre.google/sre-book/evolving-sre-engagement-model/>，检索于 2026-08-07（§8）

[93] Google SRE Book, “Postmortem Culture: Learning from Failure.” <https://sre.google/sre-book/postmortem-culture/>，检索于 2026-08-07（§4、§8）

[94] Google SRE Workbook，`sre.google/workbook/on-call/`，检索于 2026-08-07（§28；**同上，现由上册第 3 章 §3.6 引用**）

[95] Martin Fowler 官方博客，“Technical Debt” / “Technical Debt Quadrant.” <https://martinfowler.com/bliki/TechnicalDebt.html>，<https://martinfowler.com/bliki/TechnicalDebtQuadrant.html>，检索于 2026-08-07（§6）

[96] Martin Fowler 官方网站，“CanaryRelease” / “Feature Toggles (aka Feature Flags).” <https://martinfowler.com/bliki/CanaryRelease.html>，<https://martinfowler.com/articles/feature-toggles.html>，检索于 2026-08-07（§8）

[97] LaunchDarkly 官方文档，“Percentage rollouts.” <https://launchdarkly.com/docs/home/releases/percentage-rollouts>，检索于 2026-08-07（§8）

[98] LaunchDarkly 官方文档，“Targeting rules.” <https://launchdarkly.com/docs/home/flags/target-rules>，检索于 2026-08-07（§8）

[99] “User stickiness”, Google Analytics 官方帮助文档. <https://support.google.com/analytics/answer/12993725?hl=en>，检索于 2026-08-07（§8）

[100] “Funnels Advanced Concepts”, Mixpanel 官方文档. <https://docs.mixpanel.com/docs/reports/funnels/funnels-advanced>，检索于 2026-08-07（§8）

[101] “What is Feature Adoption?”, Pendo.io 官方词条库. <https://www.pendo.io/glossary/feature-adoption/>，检索于 2026-08-07（§8；页面仅含公式，不含“6.4%”等基准数字，网传该数字系编造）

[102] Qwen2.5-72B-Instruct model card. <https://huggingface.co/Qwen/Qwen2.5-72B-Instruct>，检索于 2026-08-07（§14）

[103] Qwen2.5-7B-Instruct LICENSE 文件（Apache 2.0）. <https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/LICENSE>，检索于 2026-08-07（§14）

[104] THUDM/glm-4-9b-hf model card. <https://huggingface.co/THUDM/glm-4-9b-hf>，检索于 2026-08-07（§14、§23）

[105] THUDM/glm-4-9b-hf LICENSE 文件. <https://huggingface.co/THUDM/glm-4-9b-hf/blob/main/LICENSE>，检索于 2026-08-07（§14、§23）

[106] DeepSeek-V3 LICENSE-MODEL. <https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/main/LICENSE-MODEL>，检索于 2026-08-07（§14、§23）

[107] DeepSeek-V3 README（671B 总参数/37B 激活，无法单机部署）. <https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/main/README.md>，检索于 2026-08-07（§14、§23）

[108] moonshotai/Kimi-K2-Instruct model card（1T 总参数/32B 激活，Modified MIT License 声明）. <https://huggingface.co/moonshotai/Kimi-K2-Instruct>，检索于 2026-08-07（§14、§23）

[109] Qwen2.5-3B-Instruct LICENSE（Qwen RESEARCH LICENSE AGREEMENT 原文）. <https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE>，检索于 2026-08-07（§23）

[110] DeepSeek-R1-Distill-Qwen-32B model card 与 NVIDIA System Card（显存官方数字）. <https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B>，<https://build.nvidia.com/deepseek-ai/deepseek-r1-distill-qwen-32b/systemcard>，检索于 2026-08-07（§23；页面本身抓取受限，数字经多信源交叉验证，存疑，见正文说明）

[111] VolcEngine 官方文档中心（火山方舟）. <https://docs.volcengine.com/docs/82379/1494384>，检索于 2026-08-07（§23；仅取导航结构，私有化条款未核实，存疑）

[112] 阿里云百炼计费规则与部署说明（摘要转述）. <https://help.aliyun.com/zh/model-studio/product-billing>，<https://help.aliyun.com/zh/model-studio/model-deployment-introduction>，检索于 2026-08-07（§23；部分条款复核时未能重新定位原文，存疑）

[113] 腾讯云大模型知识引擎产品文档目录. <https://cloud.tencent.com/document/product/1759>，检索于 2026-08-07（§23；未逐句核对正文，存疑）

[114] 昇思 MindSpore 社区官方文档（MindIE 产品定位、CANN 版本配套机制、1.0.RC1 版本支持模型清单）. <https://www.mindspore.cn/>，检索于 2026-08-07（§24；域名级来源，转述性质，具体页面路径未逐一核对）

[115] 达梦技术社区，《达梦向量数据开发入门手册》. <https://eco.dameng.com/community/post/20260316114022A1XPX9ZSU3Z43HEN6B>，检索于 2026-08-07（§24）

[116] 统信 UOS 官方知识分享平台（“UOS 1071 本地大模型配置手册”标题级信息）. <https://faq.uniontech.com/>，检索于 2026-08-07（§24；域名级来源，具体页面路径未逐一核对）

[117] Higress 官方博客与 GitHub 仓库. <https://higress.cn/>，检索于 2026-08-07（§24；未找到针对麒麟/统信 UOS/ARM64 的专门官方支持声明）

[118] Palantir 官方文档，“Overview • Ontology • Palantir.” <https://www.palantir.com/docs/foundry/ontology/overview>，检索于 2026-08-07（§4）

[119] Introducing the Model Context Protocol — Anthropic 官方新闻，2024-11-25，<https://www.anthropic.com/news/model-context-protocol>，检索于 2026-08-07（§15；点名 Block、Apollo 为早期采用者；Sourcegraph 官方博客确认接入 MCP 支持，属于公告中“正在对接 MCP 的开发工具公司”一类，与 Block/Apollo 的“early adopter”身份需区分表述）

[120] Apache Kafka 官方文档，“Introduction.” <https://kafka.apache.org/intro>，检索于 2026-08-07（§16）

[121] Pydantic 官方文档. <https://pydantic.dev/docs/validation/latest/get-started/>，检索于 2026-08-07（§16）

[122] microsoft/graphrag 官方文档，“Query Overview.” <https://raw.githubusercontent.com/microsoft/graphrag/main/docs/query/overview.md>，检索于 2026-08-07（§12；Local/Global/DRIFT/Basic Search 术语为产品化库新增，非原论文内容）

---

## D.4 法规与监管文件（中国）

[123] 《中华人民共和国网络安全法》— 中央网络安全和信息化委员会办公室，<https://www.cac.gov.cn/2016-11/07/c_1119867116_2.htm>，检索于 2026-08-07（§25；官方发布，已抓取原文逐字核对）

[124] 《中华人民共和国数据安全法》— 中央网络安全和信息化委员会办公室，<https://www.cac.gov.cn/2021-06/11/c_1624994566919140.htm>，检索于 2026-08-07（§25；官方发布，已抓取原文逐字核对）

[125] 《中华人民共和国个人信息保护法》— 中国人大网，<http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html>，检索于 2026-08-07（§25；官网直连 SSL 握手失败，经 jina.ai 只读代理抓取核对）

[126] 网络安全等级保护相关国家标准：GB/T 22240-2020（定级指南）、GB/T 22239-2019（基本要求）、GB/T 25070-2019（设计技术要求）、GB/T 28448-2019（测评要求）、GB/T 28449-2018（测评过程指南）（§25；国家标准委官方标准号，本书未逐条核对国标全文，正式引用具体技术条文前需查阅国标原文）

[127] 等保定级流程、测评周期的多篇第三方技术文章综合转述（§25；具体来源未在调研阶段逐一存档 URL，标注为二手信息，未见官方文件逐字核对，正式引用前建议以官方渠道确认）

[128] 《生成式人工智能服务管理暂行办法》— 中央网络安全和信息化委员会办公室，<https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm>，检索于 2026-08-07（§25；官方发布，curl 直抓 HTML 核对）

[129] 大模型备案材料清单与流程的多篇第三方开发者社区文章综合转述（阿里云/火山引擎开发者社区、知乎等）（§25；标注为二手信息，未找到网信办官方公布的独立操作细则页面）

[130] 《促进和规范数据跨境流动规定》— 中央网络安全和信息化委员会办公室，<https://www.cac.gov.cn/2024-03/22/c_1712776611775634.htm>，检索于 2026-08-07（§25；官方发布，curl 直抓核对；第三/四/五/六条负面清单/自贸区豁免细节未逐条核对，引用需二次核对）

[131] 国家金融监督管理总局《关于银行业保险业人工智能安全开发应用的指导意见》（金发〔2026〕8号）— 国家金融监督管理总局官网，<https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html?docId=1261784&itemId=&generaltype=1>，检索于 2026-08-07（§25；curl 直抓官网原文并与湖南省人民政府转载页交叉比对，正文逐字一致；文号仅在转载页正文可见，官网页面渲染未直接显示，文号本身待人工二次核实）

[132] 央行科技司司长公开表态，转引自“安全内参”媒体报道（§25；非官方文件原文，标注为官员表态而非法规条文）

[133] 国家药监局器审中心《人工智能医疗器械注册审查指导原则》（2022年第8号通告）及《人工智能医用软件产品分类界定指导原则》（2021年第47号通告）— 国家药品监督管理局官网 nmpa.gov.cn，检索于 2026-08-07（§25；经 WebSearch 定位官方通告页/jina.ai 代理核对；47号通告“施行日期”与“落款日期”存在表述差异，正文未见“自……施行”字样）

[134] 《互联网诊疗监管细则（试行）》（国卫办医发〔2022〕2号）— 国家卫生健康委员会官网，<https://www.nhc.gov.cn/yzygj/c100068/202203/2072f0e8988249e59d942e1b2a933916.shtml>，检索于 2026-08-07（§25；国家卫生健康委办公厅、国家中医药局办公室联合印发，2022年2月8日，jina.ai 代理核对；正文与本书曾经误引的“AI 不得替代医师”整句系杜撰不同，本条为审计修正后的准确文号与措辞）

[135] 《银行保险机构信息科技外包风险监管办法》（银保监办发〔2021〕141号）第三十二条 — 国务院政府网转发页，<https://www.gov.cn/zhengce/zhengceku/2022-01/25/content_5670294.htm>，检索于 2026-08-07（§21、§22；已抓取原文核对，并做多信源交叉验证）

[136] 《银行业金融机构重要信息系统投产及变更管理办法》（银监**办**发〔2009〕437号）第十四/十八/十九条（§22；文号经国家金融监督管理总局官网《继续有效主要规范性文件目录》核对，条文经转载全文页交叉核对；审计发现早期草稿曾漏写“办”字，正确文号为“银监办发”）

[137] 《商业银行业务连续性监管指引》（银监发〔2011〕104号）第二十五条（§22；已抓取上海市发改委转发的全文页核对，并做多信源交叉验证）

[138] 《银行业金融机构销售专区录音录像管理暂行规定》（银监办发〔2017〕110号）（§22；经 curl 直抓法规转载全文页核对逐条条文）

[139] 《关于规范中央企业采购管理工作的指导意见》（国资发改革规〔2024〕53号）— 国资委官网，<http://www.sasac.gov.cn/n2588035/n2588320/n2588335/c31372608/content.html>，检索于 2026-08-07（§21、§22；经 curl 直抓并逐句核对）

[140] 《全国一体化政务服务平台移动端建设指南》《全国一体化政务大数据体系建设指南》相关内容（§22；来源为北京市政府门户网站、温州市政务服务网转载页面，地方政府网站对国办文件的二次转载，非国务院政府网原文直抓，未逐句核对，引用时需自行以 gov.cn 原文复核）

[141] 涉密与非涉密计算机物理隔离原则，综合多篇转述《计算机信息系统国际联网保密管理规定》等文件的搜索摘要（§22；未抓取到任一官方保密局原文页面，未获得具体条款编号，因多方转述内容高度一致暂时采信，标注为存疑）

---

## D.5 行业报告与调研

[142] James Ryseff, Brandon de Bruhl, Sydne J. Newberry. *The Root Causes of Failure for Artificial Intelligence Projects*. RAND Corporation, 2024. <https://www.rand.org/content/dam/rand/pubs/research_reports/RRA2600/RRA2680-1/RAND_RRA2680-1.pdf>，检索于 2026-08-07（§7；正文已核实书中曾流传的“RAND 80% 失败率”实为报告转引的供应商 CEO 采访发言，非 RAND 自身研究结论，引用时已加限定）

[143] Aditya Challapally, Chris Pease, Ramesh Raskar, Pradyumna Chari. *The GenAI Divide: State of AI in Business 2025*. MIT NANDA, 2025-07. <https://valtao.com/wp-content/uploads/2025/11/Rapport-MIT.pdf>，检索于 2026-08-07（§2、§7、§8；第三方 PDF 镜像，内容与 MIT 官方版本一致，官方地址对自动化抓取返回图片型 PDF 或跳转，无法直接抓取正文；“销售与市场预算占比”数字摘要框与正文表述不一致（50%/70%），引用时取“半数以上”保守表述）

[144] Gartner, “Gartner Predicts 30 Percent of Generative AI Projects Will Be Abandoned After Proof of Concept By End of 2025”，官方新闻稿，2024-07-29. <https://www.gartner.com/en/newsroom/press-releases/2024-07-29-gartner-predicts-30-percent-of-generative-ai-projects-will-be-abandoned-after-proof-of-concept-by-end-of-2025>，检索于 2026-08-07（§7；标题与日期经媒体交叉确认，正文因官网返回 403 未能逐字核对）

[145] Gartner, “Gartner Predicts Over 40% of Agentic AI Projects Will Be Canceled by End of 2027”，官方新闻稿，2025-06-25. <https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027>，检索于 2026-08-07（§7；同上，正文未逐字核对）

[146] BCG, “AI Adoption in 2024: 74% of Companies Struggle to Achieve and Scale Value”，官方新闻稿，2024-10-24. <https://www.bcg.com/press/24october2024-ai-adoption-in-2024-74-of-companies-struggle-to-achieve-and-scale-value>，检索于 2026-08-07（§7；标题与核心数字经搜索引擎摘要交叉确认，正文因官网返回 403 未能逐字核对）

[147] “Do 70% of change initiatives really fail?”，转述 Mark Hughes (2011), *Journal of Change Management*. <https://strategyu.co/do-70-percent-of-change-initiatives-really-fail/>，检索于 2026-08-07（§7；正文已核实全书曾误引的“70% 变革失败率”是被广泛引用但缺乏原始实证支撑的僵尸数字，本条来源本身就是对这一说法的溯源与质疑）

[148] “2025 SaaS Performance Metrics”. Benchmarkit. <https://www.benchmarkit.ai/2025benchmarks>，检索于 2026-08-07（§3；基于多家 SaaS 公司财务数据的行业基准报告）

[149] “智能超参数”《中国大模型中标项目监测与洞察报告（2025）》，经“智慧城市行业分析”网站转载. <https://www.smartcity.team/news/2025%E5%B9%B4ai%E5%A4%A7%E6%A8%A1%E5%9E%8B%E6%8B%9B%E6%8A%95%E6%A0%87%E6%80%BB%E7%BB%93/>，检索于 2026-08-07（§21；二手行业分析报告，非官方统计，样本仅覆盖公开披露的中标信息；“十大主要大模型厂商的中标项目中”这一限定范围在早期草稿中曾被省略，审计后已订正）

[150] 澎湃新闻转载“数智前线”文章. <https://www.thepaper.cn/newsDetail_forward_27782592>，2024-06-20，检索于 2026-08-07（§21；二手转述，未找到“数智前线”官方原始报告页面）

[151] 《矿鸿生态发展白皮书（2026）》相关报道（据行业媒体转引“已完成 935 款产品的测试认证”）（§18；未能定位到白皮书官方发布页面的直接 URL，检索于 2026-08-07；该数字随时间推移会继续变化，早前流传的“300 多款装备认证”已过时，不应再使用）

[152] “Product Adoption Rate | Formula + Calculation Example”. Wall Street Prep. <https://www.wallstreetprep.com/knowledge/product-adoption-rate/>，检索于 2026-08-07（§8）

[153] “SaaS DAU/MAU Ratio Calculator” 及行业基准综合检索结果. PayProGlobal. <https://payproglobal.com/saas-metrics-calculators/saas-dau-mau-ratio-calculator/>，检索于 2026-08-07（§8；多篇二级来源交叉给出的方向性区间，非单一权威基准）

[154] “Employee Burnout, Part 1: The 5 Main Causes”. Gallup. <https://www.gallup.com/workplace/288539/employee-burnout-biggest-myth.aspx>，检索于 2026-08-07（§3；63%/2.6x 两条数字的原始出处，经 ClickInsights 合并转述为一句，非 Gallup 原文的逐字排列）

[155] 员工培训与高管信心落差的综合检索结果（约 45% 员工反映新软件上线无配套培训；79% 高管“有信心” vs 28% 员工认为“获得足够培训”），二级来源综合，质量等级中等，仅作方向性佐证，不作为精确统计基准引用（§4、§8）

---

## D.6 从业者文章、媒体报道与社区讨论

[156] “Forward Deployed AI Engineer: Career & Technical Guide”. sundeepteki.org. <https://www.sundeepteki.org/advice/forward-deployed-ai-engineer>，检索于 2026-08-07（§1）

[157] “What Is a Forward Deployed Engineer? Role, Skills, and Why It Matters”. DataCamp. <https://www.datacamp.com/blog/what-is-forward-deployed-engineer>，检索于 2026-08-07（§1；正文已核实并订正该文“own production delivery”表述，原文为“owns”）

[158] “What are Forward Deployed Engineers, and why are they so in demand?”. The Pragmatic Engineer. <https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers>，检索于 2026-08-07（§1）

[159] “Forward Deployed Engineer — The Complete 2026 Guide”. Dexity Substack. <https://dexity.substack.com/p/forward-deployed-engineer-the-complete>，检索于 2026-08-07（§1；第三方从业者自述博客，非公司官方来源，质量等级较低，仅作旁证）

[160] “'驻场交付工程师'成 AI 领域全新热门职业，岗位需求今年已增长逾 800%”. 新浪财经，发布于 2025-11-10. <https://finance.sina.com.cn/tech/digi/2025-11-10/doc-infwxhkr1411937.shtml>，检索于 2026-08-07（§1）

[161] “BOSS直聘：AI岗位需求'井喷式'增长，复合型人才受市场追捧”. 光明网. <https://edu.gmw.cn/2026-01/23/content_38554066.htm>，检索于 2026-08-07（§1）

[162] “Assumptions and Dependencies Clause Samples”. Law Insider 合同条款数据库. <https://www.lawinsider.com/clause/assumptions-and-dependencies>，检索于 2026-08-07（§2、§5；收录真实签署合同片段，经 curl 抓取原始 HTML 逐字核对）

[163] Law Insider，“Out of Scope Clause Examples” / “Assumptions Clause Examples”. <https://www.lawinsider.com/clause/out-of-scope>，<https://www.lawinsider.com/clause/assumptions>，检索于 2026-08-07（§5；经 curl 抓取原始 HTML 逐字核对确认）

[164] “The Four Big Risks”. Marty Cagan, Silicon Valley Product Group. <https://www.svpg.com/four-big-risks/>，检索于 2026-08-07（§2、§6）

[165] “Forward Deployed Engineers”. Marty Cagan, Silicon Valley Product Group. <https://www.svpg.com/forward-deployed-engineers/>，检索于 2026-08-07（§3、§28）

[166] “Consulting SOW template: scope, deliverables, KPIs, and exit criteria”. nmsconsulting.com. <https://nmsconsulting.com/consulting-sow-template/>，检索于 2026-08-07（§2、§5、§6）

[167] “5 Scripts You Can Use to Handle Project Scope Creep”. FreshBooks 官方博客. <https://www.freshbooks.com/blog/how-to-handle-scope-creep-5-scripts-you-can-use-now>，检索于 2026-08-07（§2、§3、§5；专业服务/咨询行业公开话术素材，经抓取核对逐字确认）

[168] “Anthropic's Guide to AI Agent Evals”. Inkeep. <https://inkeep.com/blog/anthropic-s-guide-to-ai-agent-evals-what-support-teams-need>，检索于 2026-08-07（§2；第三方转述，非 Anthropic 官方一手材料，质量等级需谨慎对待）

[169] “How To Write Excellent Acceptance Criteria (With Examples)”. cpoclub.com. <https://cpoclub.com/product-development/how-to-write-excellent-acceptance-criteria-with-examples/>，检索于 2026-08-07（§2；审计特别说明：本书初稿曾从该站点编造 4 个“验收标准示例”引文，原页面实际讲的是 ATM 认证，与本书正文所述内容完全无关，编造部分已在正文全部删除；本条仅保留该文标题本身作为真实存在的延伸阅读，读者引用前应自行核对原文与任何转述是否一致）

[170] “Identify Champions in B2B Accounts: 2026 Guide”. origami.chat. <https://origami.chat/blog/identify-champions-b2b-accounts>，检索于 2026-08-07（§2、§8；客户成功/销售领域方法论，迁移到内部推广场景需读者自行调整话术）

[171] “Best Change Champions and Agents Guide for Managing Champion Networks”. OCM Solution. <https://www.ocmsolution.com/change-champion-network/>，检索于 2026-08-07（§2、§8；转述 Prosci 变革管理方法论，未直接核对 Prosci 官方原始文档，“1:60”比例与“5%–10%工时”数字来自该转述来源，应表述为行业经验基准而非精确统计值）

[172] “Your ERP Hypercare Checklist And Post-Go-Live Support Plan”. Panorama Consulting. <https://www.panorama-consulting.com/erp-hypercare-checklist/>，检索于 2026-08-07（§2、§7、§8；按业务条线的检查清单具体条目为一手来源，Hypercare 定义与时长部分来自检索摘要综合，未逐篇核实单句出处）

[173] “Examining the Risks of IT Hero Culture”. Carmichael, M. ISACA Newsletter Vol. 13, 2024. <https://www.isaca.org/resources/news-and-trends/newsletters/atisaca/2024/volume-13/examining-the-risks-of-it-hero-culture>，检索于 2026-08-07（§3）

[174] “Your AI Pilot Nailed the Demo. Here's Why It Will Never Make It to Production”. HackerNoon，发布于 2026-07-20. <https://hackernoon.com/your-ai-pilot-nailed-the-demo-heres-why-it-will-never-make-it-to-production>，检索于 2026-08-07（§3）

[175] “On the Forward Deployed Engineer...”. Thomas Otter Substack，发布于 2025-12-14. <https://thomasotter.substack.com/p/on-the-forward-deployed-engineer>，检索于 2026-08-07（§3）

[176] “Protecting Your Solutions Masters from 'Demo Monkey' Burnout”. ClickInsights. <https://www.clickinsights.asia/post/protecting-your-solutions-masters-from-demo-monkey-burnout>，检索于 2026-08-07（§3；公司博客，实务性材料，非学术研究）

[177] “#112 Avoiding Being a Demo Jockey”. We The Sales Engineers 播客节目页. <https://wethesalesengineers.com/112-avoiding-being-a-demo-jockey/>，检索于 2026-08-07（§3）

[178] Vuksanovich, D. “What Should An SE Do When 'They Just Want A Demo'?”. LinkedIn 长文. <https://www.linkedin.com/pulse/what-should-se-do-when-just-want-demo-dan-vuksanovich>，检索于 2026-08-07（§3；从业者个人观点，非机构研究）

[179] “So You Want to Hire a Forward Deployed Engineer”. First Round Review. <https://review.firstround.com/so-you-want-to-hire-a-forward-deployed-engineer/>，检索于 2026-08-07（§4、§6）

[180] “Contextual Inquiry: Inspire Design by Observing and Interviewing Users in Their Context”. Nielsen Norman Group. <https://www.nngroup.com/articles/contextual-inquiry/>，检索于 2026-08-07（§4）

[181] “Why Field-Study Sessions Go Wrong: 5 Recommendations”. Nielsen Norman Group. <https://www.nngroup.com/articles/why-field-study-sessions-go-wrong/>，检索于 2026-08-07（§4）

[182] “Time Study Templates for Process Observation”. Systems2win. <https://www.systems2win.com/c/timeObservation.htm>，检索于 2026-08-07（§4）

[183] Jeff Hajek, “Time Observation Sheet”. Velaction. <https://www.velaction.com/time-observation-sheet/>，检索于 2026-08-07（§4）

[184] “Standardized Work”. Lean Enterprise Institute. <https://www.lean.org/lexicon-terms/standardized-work/>，检索于 2026-08-07（§4）

[185] “5 Steps to Service Blueprinting” / “Service Blueprints: Definition”. Nielsen Norman Group. <https://www.nngroup.com/articles/5-steps-service-blueprinting/>，<https://www.nngroup.com/articles/service-blueprints-definition/>，检索于 2026-08-07（§4）

[186] Wil van der Aalst, “Event Data”. processmining.org. <https://www.processmining.org/event-data.html>，检索于 2026-08-07（§4）

[187] Michele Hansen, “Customer Interview Script Template: Relatively New Customer (aka JTBD Switch Interview)”. <https://deployempathy.substack.com/p/customer-interview-script-template-relatively-new-customer-aka-jtbd-switch-interview-415338>，检索于 2026-08-07（§4）

[188] Bob Moesta & Chris Spiek, “The Jobs-to-be-Done Mattress Interview”. jobstobedone.org. <https://jobstobedone.org/radio/the-mattress-interview-part-one/>，检索于 2026-08-07（§4）

[189] “5 Whys”. MindTools. <https://www.mindtools.com/a3mi00v/5-whys>，检索于 2026-08-07（§4）

[190] “Laddering: A Research Interview Technique for Uncovering Core Values”. UXmatters. <https://www.uxmatters.com/mt/archives/2009/07/laddering-a-research-interview-technique-for-uncovering-core-values.php>，检索于 2026-08-07（§4）

[191] “Critical incident technique”. Wikipedia（转引 Flanagan, J.C., 1954, *Psychological Bulletin*）. <https://en.wikipedia.org/wiki/Critical_incident_technique>，检索于 2026-08-07（§4）

[192] Laura Brandenburg, “What Questions Do I Ask During Requirements Elicitation?”. Bridging the Gap. <https://www.bridging-the-gap.com/what-questions-do-i-ask-during-requirements-elicitation/>，检索于 2026-08-07（§4；反事实提问部分质量等级中等，为从业实践归纳，非学术一手来源）

[193] “Consulting Statement of Work Template & Guide”. BoldHaus. <https://boldhaus.com/blog/consulting-statement-of-work-template/>，检索于 2026-08-07（§5；范围外/假设/依赖条款写法惯例的归纳整理来源，非逐字引用）

[194] “First Response Time Benchmarks: How Fast Should Your Team Be in 2026?”. Lorikeet. <https://www.lorikeetcx.ai/articles/first-response-time-benchmark-customer-service>，检索于 2026-08-07（§5；客服 SaaS 厂商营销博客，质量等级中等，仅用于说明“响应时间存在可公开对比的中位数基准”这一方法论事实，具体数字不作为硬指标）

[195] “Production AI Agents: A Practical Checklist”. senrok.com. <https://www.senrok.com/i/production-ai-agents-checklist>，检索于 2026-08-07（§5、§7、§8；从业者博客，质量等级中等，经抓取核对逐字确认）

[196] “Change Request Form (Free Word Template)”. ProjectManager.com. <https://www.projectmanager.com/templates/change-request-form>，检索于 2026-08-07（§5；官方模板页，经抓取核对）

[197] “Thin Slicing: Enabling Continuous Data Warehousing”. Scott Ambler, Agile Data. <https://agiledata.org/essays/verticalslicing.html>，检索于 2026-08-07（§6）

[198] “Elephant Carpaccio facilitation guide”. Henrik Kniberg. <https://blog.crisp.se/2013/07/25/henrikkniberg/elephant-carpaccio-facilitation-guide>，检索于 2026-08-07（§6）

[199] “Walking Skeleton”. Ben Christel. <https://bensguide.substack.com/p/walking-skeleton>，转引 Alistair Cockburn 网站归档定义，检索于 2026-08-07（§6）

[200] Clint Shank, “Start with a Walking Skeleton”. 收录于《97 Things Every Software Architect Should Know》. <https://yoshi389111.github.io/kinokobooks/soft_en/Start_with_a_Walking_Skeleton.htm>，检索于 2026-08-07（§6）

[201] “Tracer Bullets and Prototypes”. Artima.com 对 Andy Hunt 与 Dave Thomas 的访谈，2003-04-21. <https://www.artima.com/articles/tracer-bullets-and-prototypes>，检索于 2026-08-07（§6）

[202] Ward Cunningham, “The WyCash Portfolio Management System”. 1992 OOPSLA 经验报告. <http://www.c2.com/doc/oopsla92.html>，检索于 2026-08-07（§6；c2.com 收录版本，agilealliance.org 原始整理页对自动化抓取返回 403/CAPTCHA，无法直接核对，改用本版本核实）

[203] “Demo Checklist”. DemoSecret. <https://demosecret.com/demo-checklist>，检索于 2026-08-07（§6；销售工程/DevRel 领域公开实操文章，非学术一手来源）

[204] “Demo Fails: How to Turn Challenges Into Triumphs”. Reprise. <https://www.reprise.com/resources/blog/demo-fails-how-to-turn-challenges-into-triumphs>，检索于 2026-08-07（§6；同上性质）

[205] “How to Build Human-in-the-Loop Oversight for AI Agents”. Galileo AI 官方博客. <https://galileo.ai/blog/human-in-the-loop-agent-oversight>，检索于 2026-08-07（§7、§8）

[206] “Technical vs Business Metrics”. Octocore. <https://www.octocore.com.br/en/blog/technical-vs-business-metrics/>，检索于 2026-08-07（§8）

[207] “Product Launch Timeline: Planning Guide and Task Checklist”. Userpilot. <https://userpilot.com/blog/product-launch-timeline/>，检索于 2026-08-07（§8；消费级产品场景，需按企业 AI 场景适配改写）

[208] “The perfect 30-60-90 day plan for a new customer success leader”. ChurnZero. <https://churnzero.com/blog/new-customer-success-leader-30-60-90-day-plan/>，检索于 2026-08-07（§8；原场景为“新员工上任计划”，迁移到系统上线跟进场景为笔者归纳改写）

[209] “What is P99 latency?”. SRE School. <https://sreschool.com/blog/p99-latency/>，检索于 2026-08-07（§8）

[210] Marc Brooker, “Exponential Backoff And Jitter”. *AWS Architecture Blog*，2015-03-27（2023-05 更新）. <https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/>，检索于 2026-08-07（§10；经 r.jina.ai 代理逐字核对正文；文中算法配图未提供可复制文本，正文对应代码为据其思路复现，非逐字摘录）

[211] Chroma 官方研究报告（`RecursiveCharacterTextSplitter` vs `ClusterSemanticChunker` 对比数据），本书调研笔记核实（§11；注意 Chroma 为被测方法提出方之一）

[212] LlamaIndex 官方默认分块参数（`chunk_size=1024, chunk_overlap=20`），经本书调研笔记核实（§11）

[213] Pinecone 官方分块策略文档，经本书调研笔记核实（§11；全文未给出具体重叠百分比建议）

[214] Elastic Search Labs，rerank 深度与延迟实测工程博客，用 BM25 + BEIR 统一复测 6 款不同厂商 reranker 的延迟（§12、§19；方法论公开但 Elastic 自身也是被测 reranker 厂商之一，存在潜在利益关联；具体文章 URL 未留存，仅引用其揭示的“不同 reranker 之间存在数量级延迟差异”这一方向性结论，不作为绝对数字使用）

[215] GPUStack 技术博客《没有 GPU，还能跑大模型吗？vLLM vs llama.cpp 实测对比》. <https://www.cnblogs.com/gpustack/p/20249257>，检索于 2026-08-07（§24；第三方原创实测，非官方数据、非本项目数据）

[216] 华为官方案例页面《AI 质检 2023》. <https://e.huawei.com/cn/case-studies/industries/manufacturing/ai-quality-inspection-2023>，检索于 2026-08-07（§17；富士康、宝德计算机、美的集团数据；正文已核实并订正曾误写为“浪潮”的客户名，正确为“宝德计算机”）

[217] “John Deere transforms agriculture with AI”. OpenAI 官方案例页. <https://openai.com/index/john-deere-justin-rose/>，检索于 2026-08-07（§17）

[218] “See & Spray 59 Percent Herbicide Savings”. John Deere US 官方新闻. <https://www.deere.com/en-us/john-deere-news/see-spray-59-percent-herbicide-savings>，检索于 2026-08-07（§17；正文已核实，官方年均口径为 59%/2024、约 50%/2025，网传“70%”须限定为峰值数字，不可当年均值使用）

[219] “Farmers Use John Deere See & Spray Across 5 Million Acres in 2025”（转载 John Deere 官方新闻稿）. Precision Farming Dealer. <https://www.precisionfarmingdealer.com/articles/6834-farmers-use-john-deere-see-and-spray-across-5-million-acres-in-2025>，检索于 2026-08-07（§17）

[220] 华为与山东能源集团“盘古矿山大模型” — 《中国能源报》，2025-12-22. <https://paper.people.com.cn/zgnyb/pc/content/202512/22/content_30126939.html>，检索于 2026-08-07（§18；“现已在 180 多类场景落地应用”及“井下少人、减人甚至无人化必成常态”）

[221] 华为官方新闻——伊敏华能智能矿山. <https://www.huawei.com/cn/news/2025/5/yimin-huaneng-intelligent-mining>，检索于 2026-08-07（§18；全球首个百台级无人电动矿卡集群“华能睿驰”，内蒙古伊敏露天矿，作为矿山 AI 规模化落地的行业背景对照，与本章虚构的地下煤矿合成案例不属同一项目）

[222] “Airline held liable for its chatbot giving passenger bad advice”. BBC. <https://www.bbc.com/travel/article/20240222-air-canada-chatbot-misinformation-what-travellers-should-know>，检索于 2026-08-07（§20）

[223] “Moffatt v. Air Canada: Bereavement Fares”. welpartners.com. <https://welpartners.com/blog/2024/03/moffatt-v-air-canada-bereavement-fares-do-your-research/>，检索于 2026-08-07（§20）

[224] “Incident 622: Chevrolet Dealer Chatbot Agrees to Sell Tahoe for $1”. AI Incident Database. <https://incidentdatabase.ai/cite/622/>，检索于 2026-08-07（§20）

[225] “MD Anderson Benches IBM Watson In Setback For Artificial Intelligence In Medicine”. Forbes. <https://www.forbes.com/sites/matthewherper/2017/02/19/md-anderson-benches-ibm-watson-in-setback-for-artificial-intelligence-in-medicine/>，检索于 2026-08-07（§20）

[226] “IBM pitched its Watson supercomputer as a revolution in cancer care. It's nowhere close”. STAT News（经 Wayback Machine 2018 年快照核对）. <https://www.statnews.com/2017/09/05/watson-ibm-cancer/>，检索于 2026-08-07（§20）

[227] “IBM's Watson recommended 'unsafe and incorrect' cancer treatments”. STAT News. <https://www.statnews.com/2018/07/25/ibm-watson-recommended-unsafe-incorrect-treatments/>，检索于 2026-08-07（§20；该报道主题为 Memorial Sloan Kettering 训练数据问题，与 MD Anderson 项目终止是相关但不同的两条新闻线，正文曾误将两者混为一谈，审计后已区分表述）

[228] “ZILLOW GROUP, INC. Form 10-K FY2021”. SEC EDGAR. <https://www.sec.gov/Archives/edgar/data/1617640/000161764022000013/z-20211231.htm>，检索于 2026-08-07（§20）

[229] 《AI tools for Forward Deployed Engineering — Vasuman Moza, Varick Agents》. *AI Engineer* 播客，2026年7月发布（视频ID `l0FLhNqBOic`，经 YouTube oEmbed 接口核实官方标题），检索于 2026-08-07（§28）

[230] 第三方财经媒体对上述播客内容的转述报道（拼写为“Veric Agents”，与本书采用的“Varick Agents”拼写不一致，人名“Voss”经核实很可能是转录错误）（§28；本书不采用该拼写与人名，仅作为“两种拼写并存”现象的佐证列出）

[231] 驻场费用按人天报价、每月结算的通行模式描述（§21；非署名 IT 外包行业营销类文章，未提供可独立核实的具体链接，可信度低，仅作背景常识，不建议作为行业标准引用）

[232] 公开招标/邀请招标/竞争性磋商的定义与适用场景，转述自多篇对《政府采购法》及其实施条例的解读性搜索摘要（§21；未直接抓取法条原文逐句核对，建议以国务院政府网公布的《政府采购法实施条例》官方文本二次核对）

[233] 系统集成商总包分包结构、设备/应用系统集成商分类、AI 项目四类服务商画像（§21；来源为搜索摘要转述知乎等平台文章的归纳整理，非官方定义，未提供可独立核实的具体链接，存疑，仅作理解行业结构的粗粒度框架使用）

[234] 昇腾 910B 与 NVIDIA A100/H100 性能对比的矛盾数字（多篇 CSDN/第三方博客，数字互相矛盾）（§24；可信度低，仅作“存在该说法但未核实”记录）

[235] Jeremy Kahn, “Want Your Company's A.I. Project to Succeed? Don't Hand It to the Data Scientists, Says This CEO”. *Fortune*，2022-07-26（经 RAND 报告脚注 13 转引核实）（§7）

[236] 寒武纪/摩尔线程/海光对主流开源大模型的适配公告，经财联社、新浪财经、每经网等多家财经媒体交叉报道确认（§24）

[239] Kaitlin Elliott（摩根士丹利 Firmwide Artificial Intelligence 部门 Executive Director）访谈，“AI Evals in Practice with Morgan Stanley”. Scale AI 播客 *Human in the Loop* 第 13 期，2025-09-16. <https://scale.com/blog/hitl-ep13-ai-evals-in-practice>，检索于 2026-08-31（§7、§12；当事人逐字发言，引语已逐字核对原文；500 题回归集按“每次改动方案”触发，每日约 100 道为真实交互抽检，两个口径分属两件事）
[240] Louis Claxton, “The AI-Native SDLC playbook”. Anthropic 官方博客，2026-08-21. <https://claude.com/blog/the-ai-native-sdlc-playbook>，检索于 2026-08-31（§2、§12、下册技能章；引语已逐字核对：治理随智能体行动强制执行/评审队列与欠审上线两难/agent 配置变更应触发评估重跑/技能为劝导性控制而钩子为确定性兜底。口径：厂商对自身最佳实践的陈述，非独立研究）
[241] “Building an AI-native engineering team”. OpenAI 官方企业指南 PDF，2025-11. <https://cdn.openai.com/business-guides-and-resources/building-an-ai-native-engineering-team.pdf>，检索于 2026-08-31（§2；PDF 全文已逐字核对，七阶段与 “Delegate vs. review vs. own” 等引语见第 2 章参考来源）

[242] “AI in the Enterprise: Lessons from seven frontier companies”. OpenAI 官方白皮书 PDF，2025. <https://cdn.openai.com/business-guides-and-resources/ai-in-the-enterprise.pdf>，检索于 2026-08-31（§2；PDF 全文已逐字核对，“Start with evals”）

[243] “The OpenAI Deployment Company”. OpenAI 官方页面，2026-05. <https://openai.com/business/the-openai-deployment-company/>，检索于 2026-08-31（§2；经 r.jina.ai 只读代理取得正文并逐字核对 FDE 定义句）

[244] “Specs”. AWS Kiro 官方文档. <https://kiro.dev/docs/specs/>，检索于 2026-08-31（§2；已核原文两句，EARS 语法未核未引）

[245] Den Delimarsky, “Spec-driven development with AI: Get started with a new open source toolkit”. GitHub 官方博客，2025-09-02. <https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/>，检索于 2026-08-31（§2；已核原文）

[246] “State of AI-assisted Software Development”（DORA 2025）. Google Cloud DORA，2025-09. <https://dora.dev/research/2025/dora-report/>，检索于 2026-08-31（§2；只引用主页主结论一句，报告全文未逐字通读）

[247] Jason Martin, “Forward Deployed Engineering: Delivering business outcomes with AI”. Databricks 官方博客，2026-06-11. <https://www.databricks.com/blog/forward-deployed-engineering-delivering-business-outcomes-ai>，检索于 2026-08-31（§2；已核原文三处引语）

[248] “A Day in the Life of a Palantir Forward Deployed Software Engineer”. Palantir 官方博客，2020-11-02. <https://blog.palantir.com/a-day-in-the-life-of-a-palantir-forward-deployed-software-engineer-45ef2de257b1>，检索于 2026-08-31（§1；访谈体一线自述，引语已逐字核对；发布日期以页面元数据为准，网传 2022-06 为索引站噪音）

[249] “Forward Deployed Engineers and the future of software engineering”. Latent Space 对 Sierra 智能体工程负责人 Natalie Meurer 的访谈，2026-07-01. <https://www.latent.space/p/forward-deployed-engineers-aiewf>，检索于 2026-08-31（§1；引语已逐字核对）

[250] “The FDE Playbook for AI Startups with Bob McGrew”. YC Lightcone 播客，2025-09-12. <https://www.ycombinator.com/library/Mt-the-fde-playbook-for-ai-startups-with-bob-mcgrew>，检索于 2026-08-31（§21；YC 官方页面自带全文字稿，引语已逐字核对；“接触更重要问题的资格”系 McGrew 转述 Shyam Sankar）

[251] Joe Schmidt, “Trading Margin for Moat: The Rise of Services-Led Growth”. a16z 官方博客，2025-06-04. <https://a16z.com/services-led-growth/>，检索于 2026-08-31（§21；引语与 ServiceNow/Workday 上市毛利数字已逐字核对该文，本书未另查招股书）

[252] Barry McCardel, “Understanding Forward Deployed Engineering”. 个人博客，原发 2024-11、更新 2026-03. <https://www.barry.ooo/posts/fde-culture>，检索于 2026-08-31（§21；作者曾任 Palantir Deployment Strategist 约 5 年、现 Hex 创始人/CEO，**个人观点文章，属内部亲历者一手判断**，引语已逐字核对）

[253] 张保文《中国 To B 软件，走出“亏损式增长”的陷阱》. 微信公众号“牛透社”原创、36氪经授权发布，2024-08-06. <https://36kr.com/p/2894385404828288>，检索于 2026-08-31（§21；引语已逐字核对，“项目型公司”一语出自文中受访从业者（神州云合高级副总裁），系访谈转述）

[254] 陈果《企业级AI应用不赚钱……战场找错了》. 观察者网风闻专栏（作者自运营，与其公众号“陈果George”同步），2026-06-23. <https://user.guancha.cn/main/content?id=1674960>，检索于 2026-08-31（§21；作者为前 BCG Platinion 董事总经理、前 IBM 咨询全球合伙人，**个人观点专栏，非统计结论**，引语已逐字核对）

[255] Evan Schuman, “Anthropic’s financial agents expose forward deployed engineers as new AI limiting factor”. CIO.com，2026-05-06. <https://www.cio.com/article/4167981/anthropics-financial-agents-expose-forward-deployed-engineers-as-new-ai-limiting-factor.html>，检索于 2026-08-31（§8；引语已逐字核对。**口径：Gartner 分析师 Coqueiro 经媒体发表的观点，非 Gartner 官方报告**；同文“2028 年 70% 企业放弃”系分析师个人预测，本书不据此立论）

[256] “Global Lighthouse Network Recognizes 23 New Sites, Launches AI Platform for Industrial Transformation”. 世界经济论坛官方新闻稿，2026-01-15. <https://www.weforum.org/press/2026/01/global-lighthouse-network-recognizes-23-new-sites-launches-ai-platform-for-industrial-transformation/>，检索于 2026-08-31（§22；西门子数控南京、美的芜湖、昆岭薄膜条目，引语与数字已逐字核对）

[257] “Siemens’ AI-powered Nanjing facility named World Economic Forum Global Lighthouse”. 西门子全球新闻中心官方新闻稿，2026-01-15. <https://press.siemens.com/global/en/pressrelease/siemens-ai-powered-nanjing-facility-named-world-economic-forum-global-lighthouse>，检索于 2026-08-31（§22；与 [256] 双源互证，“Compared to 2022…by 2024”基线口径已逐字核对）

[258] 美的集团《2025年年度报告》（000333.SZ）. 巨潮资讯网法定披露，2026-03-31. <http://static.cninfo.com.cn/finalpage/2026-03-31/1225065145.PDF>，检索于 2026-08-31（§22；“数字化套餐”推广 9 新 7 老工厂、员工自主搭建智能体 1.35 万个等表述已逐字核对选段）

[259] 潍柴动力《2025年年度报告》（000338.SZ）. 巨潮资讯网法定披露，2026-03-27. <http://static.cninfo.com.cn/finalpage/2026-03-27/1225037559.PDF>，检索于 2026-08-31（§22；“智慧云”8000 家服务网点/240 万台发动机远程运维、内训师队伍等表述已逐字核对选段，与 [260] 交叉互证）

[260] 《2025年度领航级智能工厂培育名单》（工信厅联通装函〔2025〕486号）. 工信部等六部门，2025-11-24. <https://wap.miit.gov.cn/jgsj/zbys/wjfb/art/2025/art_a5307d7932024d56bf3be162b2ed065b.html>，检索于 2026-08-31（§22；通知逐字，15 家名单为官方名单图逐字转录；四级梯度与遴选程序出自本文件）

[261] 《“人工智能+制造”专项行动实施意见》（工信部联科〔2025〕279号）. 八部门 2025-12-25 印发，国家数据局官网全文（含附件2《制造业企业人工智能应用指南》）. <https://www.nda.gov.cn/sjj/zwgk/zcfb/0112/20260107214358696030895_pc.html>，检索于 2026-08-31（§22；引语已逐字核对；未抓取 miit.gov.cn 原发页，以联合印发部门官网全文为准）

[262] 《工业和信息化领域数据安全管理办法（试行）》（工信部网安〔2022〕166号）. 2023-01-01 施行，国务院政府网政策库全文. <https://www.gov.cn/zhengce/zhengceku/2022-12/14/content_5731918.htm>，检索于 2026-08-31（§22；八章四十二条全文逐字，三级分级见第八条）

[263] 《工业控制系统网络安全防护指南》（工信部网安〔2024〕14号）. 2024-01-19 印发，国务院政府网全文. <https://www.gov.cn/zhengce/zhengceku/202402/content_6929643.htm>，检索于 2026-08-31（§22；33 项基线要求全文逐字）

[264] “Introducing the Model Context Protocol”. Anthropic 官方发布公告，2024-11-25. <https://www.anthropic.com/news/model-context-protocol>，检索于 2026-08-31（§2；逐字原文；页面无署期，日期据 [268] 双源“one year after the release”周年表述互证）

[265] “Model context protocol (MCP)”. OpenAI Agents SDK 官方文档. <https://openai.github.io/openai-agents-python/mcp/>，检索于 2026-08-31（§2；文档页逐字；仅用于证明“竞争对手官方 SDK 原生支持该协议”这一事实；宣布时间 2025-03-26 为媒体口径，未据以立论）

[266] “Securing the Model Context Protocol: Building a safer agentic future on Windows”. 微软 Windows 官方博客，2025-05-19. <https://blogs.windows.com/windowsexperience/2025/05/19/securing-the-model-context-protocol-building-a-safer-agentic-future-on-windows/>，检索于 2026-08-31（§2；逐字原文；Windows 11 以 MCP 为“智能体计算的基础层”，配 MCP Registry 与强制代码签名）

[267] “支付宝MCP，让您的AI应用自动收款”. 阿里云官方技术解决方案页，及阿里云百炼帮助中心“官方 MCP 服务”目录页. <https://www.aliyun.com/solution/tech-solution/alipay-mcp>，检索于 2026-08-31（§2；官方页逐字；“支付 MCP Server”2025-04-15 联合魔搭首发的时间点出自量子位当日报道，媒体口径仅用于钉日期）

[268] “MCP joins the Agentic AI Foundation”. MCP 官方博客，2025-12-09. <https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/>，检索于 2026-08-31（§2；逐字原文，月 SDK 下载 9700 万+/活跃服务器 1 万+ 为官方口径；与 Linux 基金会同日通稿互证，后者“Fortune 500 deployments”一句无明细，不单独据以立论）

---

## D.7 如何使用本附录

- 想核对某一章某条具体数字的原始出处：先看该章末尾的“参考来源”小节找到角标编号，再回本附录按标题定位对应条目——本附录的条目文字与各章角标基本一一对应，只是去重后重新编了号。
- 想知道全书哪些结论“证据最硬”：优先看 D.2（学术论文）与 D.3（官方技术文档）中没有额外括注的条目——没有括注不代表完美无缺，但代表本书写作时做到了逐字核对原文。
- 想知道全书哪些结论“要打个问号再用”：搜索本附录里的“存疑”“转述”“未逐字核对”“抓取受限”“可信度低”这几个关键词，会遇到的条目集中在 D.4（中国法规里未直接抓取原文的部分）、D.5（第三方行业报告的二手转载）与 D.6（从业者博客与媒体报道）——这不是巧合，是本书可信度分层原则的直接体现。
- 更完整的失真类型分类与逐条修正记录，见 `docs/research/CITATION-AUDIT.md`。
