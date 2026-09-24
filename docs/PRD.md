# PRD — 端到端 RAG AI 系统

> 作者：晨星 ｜ 版本：v1.0 ｜ 状态：待架构师确认

## 1. 项目信息

| 项 | 值 |
|---|---|
| Language | 中文（关键术语/指标/命令保留英文） |
| Programming Language | Python 3.13.14（核心栈）；FastAPI 0.141 + uvicorn 提供 HTTP/SSE API；**不引入 Node 前端构建链**（避免 npm 编译与额外工具链风险） |
| Project Name | `helios-ai-stack` |
| GitHub 署名 | 晨星（全部源文件头注释、LICENSE、README、git author 统一） |
| 运行环境 | Windows 11 / 16 核 CPU / **无 NVIDIA GPU** / C 盘余量 31G / 无 MSVC 与 cmake |
| 网络约束 | huggingface.co **不可达**；模型走 ModelScope 或 Ollama registry；**必须支持完全离线运行** |
| 已有可复用环境 | `C:\Users\Administrator\.workbuddy\binaries\python\envs\helios\Scripts\python.exe`（faiss-cpu 1.15.0 / fastembed 0.8.0 / onnxruntime 1.30.0 / llama_cpp_python 0.3.19 / rank-bm25 0.2.2 / pypdf 6.18.1 / fastapi 0.141.1 / uvicorn 0.53.0 / mcp 2.2.0 / tokenizers 0.23.2 / numpy 2.5.3 / mmh3 5.3.0 / diskcache 5.6.3 / pytest 8.4.2 等，全部 import 通过） |

### 1.1 原始需求复述（逐字要点）

自主构建并交付一套世界顶级端到端 AI 系统：可实际运行、性能对标业界 SOTA、可一键复现部署；技术路线为**优先复用**业界领先开源成果，能复用的一律不重写，禁止从零自研（确有必要时须书面说明理由），关键选型须记录对比依据（性能/生态/许可证/维护活跃度）；按单一职责划分模块并定义接口与错误码，每个模块独立可验证（单测 + 最小可运行示例），可组合成完整链路；工程纪律上禁止遗留 TODO 与部分可用，依赖版本锁定、干净环境一键复现、附带性能基线；交付源代码+测试+示例、锁定依赖清单与构建配置、架构/部署/使用文档、GitHub 仓库；验收标准为「克隆 → 一键脚本 → 端到端 demo 跑通，零手工干预」。

---

## 2. 产品定义

### 2.1 一句话定位

**一个在无 GPU 的 Windows 机器上可离线一键复现、模块化可独立验证、性能有量化基线的端到端检索增强生成（RAG）系统**。

### 2.2 产品目标（3 条，正交）

| # | 目标 | 说明 |
|---|---|---|
| G1 | **可复现** | 干净环境（仅有 Python 3.13）执行一条命令完成环境+依赖+模型准备+E2E demo 跑通，零手工干预、零网络亦可通过 |
| G2 | **可验证** | 每个模块有独立单测与最小可运行示例；全链路有 1 条 E2E 用例；检索质量与性能有量化基线，可对比对标方案 |
| G3 | **可演进** | 所有模型/存储/推理都以 Protocol（接口）抽象，同一接口下可热插拔实现（ONNX / GGUF / 远端 API / Mock），不改业务代码 |

### 2.3 成功标准（可量化）

| 指标 | 目标值 | 测量方式 |
|---|---|---|
| S1 一键复现成功率 | 全新克隆 × 3 次，`setup` 脚本均 100% 成功、E2E demo 退出码 0 | 脚本内置自检步骤，输出 PASS/FAIL |
| S2 测试完备度 | 核心模块数 ≥ 8，每模块 ≥ 3 个单测；总用例 ≥ 40；`pytest -m "not requires_model"` **全绿** | pytest 报告 + 覆盖率报告 |
| S3 检索质量 | 内置 gold 集（≥ 50 条 query-document 对）：hybrid（dense+BM25）Recall@10 ≥ 0.90；经 rerank 后 nDCG@10 相对 rerank 前 **提升 ≥ 10%** | `eval` 子命令输出 JSON 基线 |
| S4 性能基线 | 索引构建 10k chunk（384 维）≤ 60s；检索 p50 ≤ 30ms / p95 ≤ 120ms；E2E（检索+重排+生成）p50 ≤ 15s；离线 mock 链路 p50 ≤ 1s | `bench` 子命令，结果写入 `benchmarks/baseline.json` |
| S5 引用溯源 | 生成答案的每个断言均可回溯到 `chunk_id + 字符区间`，溯源命中率 = 100%（gold 集人工标注 20 条） | `eval --task citation` |
| S6 部署可用性 | `uvicorn` 启动后 `/healthz` 200，OpenAPI 文档自动生成，SSE 流式首 token ≤ 3s（本地 GGUF Qwen2.5-3B Q4_K_M） | 冒烟脚本 |

> 说明：S3/S4 中的数值为**目标值**，实际基线由 `bench` 实测产生并入库；若实测不达标，须在 README「已知差距」中列出原因与优化项，**不允许删除指标**。

---

## 3. 用户故事

| # | 用户故事 | 验收判据（可测） |
|---|---|---|
| US1 | 作为**运维/复现者**，我想在干净 Windows 机器上执行一条命令，就能完成环境搭建与 E2E demo 跑通，以便零手工干预验证系统可用性 | `scripts/setup.ps1` + `scripts/demo.ps1` 全流程退出码 0；连续 3 次全新克隆均成功 |
| US2 | 作为**知识库管理员**，我想把一个目录的 PDF/TXT/MD 批量摄入，自动完成解析→切分→去重→建索引，以便后续可检索 | `ingest --dir ./corpus` 输出统计（文档数/chunk 数/耗时）；重复文档二次摄入不产生重复 chunk（内容哈希幂等） |
| US3 | 作为**检索工程师**，我想同时用稠密向量与 BM25 做混合检索（RRF 融合），以便兼顾语义召回与关键词精确命中 | `search --mode hybrid` 返回 top-k 且每条含 `dense_rank / sparse_rank / fused_score`；gold 集 Recall@10 ≥ 0.90 |
| US4 | 作为**检索工程师**，我想对 top-50 候选做交叉编码重排得到 top-5，以便提升排序质量 | `rerank` 输出重排前后序位变化；nDCG@10 相对提升 ≥ 10%；重排耗时纳入基线 |
| US5 | 作为**终端用户**，我想就知识库提问并得到**带引用**的答案，以便核验信息来源 | API 返回 `answer + citations[{chunk_id, doc_id, span_start, span_end, quote, score}]`；每条引用可反查原文 |
| US6 | 作为**终端用户**，我想以流式方式接收答案，以便尽早看到首字 | `/v1/chat` 支持 SSE，事件类型 `token / citation / done / error`；首 token ≤ 3s |
| US7 | 作为**算法工程师**，我想一键跑出检索质量与性能基线并与对标方案（dense-only / BM25-only / 无重排）对比，以便证明选型有效 | `eval` 输出四组对照的 Recall@5/10、MRR、nDCG@10；`bench` 输出 p50/p95；结果落盘 JSON + Markdown 表 |
| US8 | 作为**模块开发者**，我想只针对某一个模块写单测并独立运行示例，以便快速定位问题 | 每个模块目录含 `tests/` 与 `examples/minimal.py`；`pytest src/<module>/tests` 可单独通过 |
| US9 | 作为**集成方**，我想通过标准 HTTP API 与 MCP 工具接入，以便被上层应用调用 | OpenAPI schema 可导出；MCP server 暴露 `search / answer` 两个 tool 且可被 mcp client 调用 |
| US10 | 作为**审计者**，我想看到每个关键选型的对比依据与许可证清单，以便确认合规与可维护性 | `docs/PRD.md` 选型表 + `docs/DEPENDENCIES.md` 许可证清单齐全，无 GPL/AGPL 传染性依赖 |

---

## 4. 模块划分与接口契约（P0）

> 单一职责 + 独立可验证。所有跨模块调用仅通过 dataclass / Protocol，**禁止**模块间直接互相 import 实现细节。

| 模块 | 唯一职责 | 输入 | 输出 | 协议/形态 | 错误码前缀 |
|---|---|---|---|---|---|
| `ingest` | 文档解析与切分、去重 | `Path / bytes + mime` | `List[Document]`（doc_id, content_hash, pages） | Python API | `E_INGEST_*` |
| `chunk` | 文本切块与 overlap | `Document` | `List[Chunk]`（chunk_id, doc_id, text, span） | Python API | `E_CHUNK_*` |
| `embed` | 文本→稠密向量 | `List[str]` | `np.ndarray[N, D]`（float32, L2 归一） | Protocol `Embedder` | `E_EMBED_*` |
| `lexical` | 稀疏/词法检索 | `query + corpus` | `List[Hit]`（BM25 分） | Protocol `LexicalIndex` | `E_LEXICAL_*` |
| `vector` | 稠密 ANN 索引与持久化 | `ndarray + ids` / `query vec` | `List[Hit]` | Protocol `VectorIndex` | `E_VECTOR_*` |
| `fuse` | 多路结果融合（RRF / 加权） | `List[List[Hit]]` | `List[Hit]` | Python API | `E_FUSE_*` |
| `rerank` | 交叉编码重排 | `query + List[Chunk]` | `List[ScoredChunk]` | Protocol `Reranker` | `E_RERANK_*` |
| `llm` | 生成（含流式） | `prompt + context` | `str` / `Iterator[str]` | Protocol `LLM` | `E_LLM_*` |
| `cite` | 引用抽取与对齐校验 | `answer + context chunks` | `List[Citation]` | Python API | `E_CITE_*` |
| `pipeline` | 编排（唯一允许串联各模块的地方） | `PipelineConfig + query` | `Answer`（answer, citations, timings, trace） | Python API | `E_PIPE_*` |
| `api` | HTTP/SSE 暴露 | HTTP 请求 | JSON / SSE | HTTP + MCP | `E_API_*` |
| `evalkit` | 质量与性能评测 | gold 集 + 配置 | `MetricsReport` (JSON/MD) | CLI | `E_EVAL_*` |

**统一错误码规范**：`E_<MODULE>_<CATEGORY>`，CATEGORY ∈ {`BAD_INPUT`, `NOT_FOUND`, `MODEL_MISSING`, `NET_DISABLED`, `TIMEOUT`, `INTERNAL`}；所有异常继承 `HeliosError(code, message, detail)`，HTTP 层映射为 4xx/5xx 并在响应体返回 `error.code`。

---

## 5. 需求池

### P0（Must have — 不完成即验收失败）

| ID | 需求 | 验收判据 |
|---|---|---|
| P0-1 | 一键脚本：`scripts/setup.ps1`（建 venv、装锁定依赖、准备模型或离线兜底）+ `scripts/demo.ps1`（跑 E2E） | 干净环境 3 次全新克隆均 100% 成功，退出码 0 |
| P0-2 | 依赖锁定：`requirements.lock.txt`（含精确版本 + sha256）+ `pyproject.toml`，禁止浮动版本 | `pip install -r requirements.lock.txt --require-hashes` 成功；`pip check` 无冲突 |
| P0-3 | 离线可运行：默认 profile = `offline`，零网络零模型零 API Key 下全部单测与 E2E 通过 | 断网（或 `HELIOS_ALLOW_NETWORK=0`）执行 `pytest` 与 `demo` 全绿 |
| P0-4 | 8+ 模块按单一职责拆分，各自独立可测，含 `examples/minimal.py` | 每个模块单测 ≥ 3，可单独 `pytest src/<m>/tests` 通过 |
| P0-5 | 完整链路：ingest → chunk → embed+lexical → hybrid fuse → rerank → LLM → citation | E2E 用例 1 条必过，输出 Answer 含 ≥1 条可回溯引用 |
| P0-6 | 引用溯源：答案携带 `chunk_id + span + quote`，可反查原文 | gold 集 20 条引用溯源命中率 100% |
| P0-7 | 评测基线：`eval`（Recall@5/10、MRR、nDCG@10）与 `bench`（p50/p95）四组对照 | 输出 `benchmarks/baseline.json` + README 表格 |
| P0-8 | 接口契约与错误码文档化，统一 `HeliosError` | `docs/ARCHITECTURE.md` 含接口表 + 错误码表；单测覆盖主要错误路径 |
| P0-9 | 依赖版本锁定 + 许可证清单（无 GPL/AGPL） | `docs/DEPENDENCIES.md` 逐项列出版本+许可证 |
| P0-10 | GitHub 仓库：README（架构/部署/使用）、LICENSE(Apache-2.0)、CONTRIBUTING、CI（GitHub Actions 跑离线单测） | 仓库可克隆，CI 绿灯，署名统一「晨星」 |
| P0-11 | 代码质量门禁：ruff 检查 0 error；无 TODO/FIXME 残留 | `ruff check .` 通过；`grep -r TODO` 无业务代码命中 |

### P1（Should have）

| ID | 需求 | 验收判据 |
|---|---|---|
| P1-1 | 真实模型本地链路：`local` profile 用 ONNX 嵌入 + GGUF 生成跑通（模型经 ModelScope 下载并缓存、sha256 校验） | `demo --profile local` 端到端成功并产出基线 |
| P1-2 | FastAPI 服务：`/healthz`、`/v1/search`、`/v1/chat`（SSE）、`/v1/ingest`、`/metrics` | OpenAPI 可导出；冒烟脚本全部 200 |
| P1-3 | MCP server：暴露 `search`、`answer` 工具 | mcp client 可调用并返回结果 |
| P1-4 | 索引持久化与增量更新（faiss index + id map + BM25 状态落盘） | 重启后加载索引无需重建；增量摄入仅追加 |
| P1-5 | 结果缓存（diskcache，按 query+配置 hash） | 二次同 query 命中缓存，延迟下降 ≥ 50% |
| P1-6 | 可观测性：结构化日志（loguru）+ trace id + 各阶段耗时埋点 | 单次请求日志含 trace_id 与各阶段 ms |
| P1-7 | 中文分词优化：BM25 中文按字符 2-gram + 英文按词切分 | 中文 query gold 集 Recall@10 相对纯空格切分提升 ≥ 5% |
| P1-8 | Web 最小界面（FastAPI 托管静态 HTML，无构建链） | 浏览器可提问并看到答案+引用高亮 |

### P2（Nice to have）

| ID | 需求 | 验收判据 |
|---|---|---|
| P2-1 | Ollama / OpenAI 兼容远端 LLM adapter | 配 profile 可切换，接口不变 |
| P2-2 | LlamaIndex / LangChain 兼容 adapter（证明自研编排层可替换） | 示例脚本可用 LlamaIndex 跑同一 gold 集 |
| P2-3 | 查询改写 / HyDE（用同一 LLM 接口实现） | gold 集 nDCG@10 不下降 |
| P2-4 | 多模态（图片 OCR 后入库） | 示例可检索图片内文字 |
| P2-5 | Docker 镜像与 `docker compose` 一键起服务（复用本机 Docker 29.7.2） | `docker compose up` 后 `/healthz` 200 |
| P2-6 | 基准对比扩展到公开数据集（如 BEIR 子集，离线内置） | 报告含与 BM25/dense-only 的对照 |

---

## 6. 关键选型对比（重点）

> 对比列统一为：**性能 / 生态 / 许可证 / 维护活跃度 / Windows 无 GPU 免编译可安装性 / 结论与理由原文**。
> 硬约束复述：Windows 11、无 GPU、无 MSVC/cmake（**任何需本地编译的包直接出局**）、Py3.13、C 盘 31G、huggingface.co 不可达。

### 6.1 向量检索库

| 候选 | 性能 | 生态 | 许可证 | 维护活跃度 | Win 无 GPU 免编译可安装性 | 结论与理由原文 |
|---|---|---|---|---|---|---|
| **faiss-cpu 1.15.0** ✅ | C++ SIMD 实现，IVF-Flat/HNSW/PQ 齐全；10 万级向量 CPU 检索毫秒级；支持 IVF-PQ 压缩省内存 | Meta 出品，事实标准；与 numpy 无缝；被无数 RAG 系统用作底座 | MIT（宽松） | 高（持续发版，pip 提供 **cp313 win_amd64 wheel**） | **本环境已装且 import 通过**，零安装风险 | **选它。** 性能天花板最高、许可证宽松、生态最大，且**已实测可 import**，是唯一零风险项；用 `IndexFlatIP`（小规模精确）+ `IndexIVFFlat`（大规模）双策略，按数据量自动切换 |
| qdrant-client（local 模式） | local 模式官方 README 自述「We just implemented Qdrant API in **pure Python**」→ 性能显著低于 C++ 实现；优势在过滤/混合检索 API 友好 | 与 fastembed 深度集成，`client.add/query` 体验好 | Apache-2.0 | 高（Qdrant 官方活跃维护） | 纯 Python，**免编译可装（pip 有 wheel）** | **不选（P2 备选）。** 免编译性 OK，但 local 模式为纯 Python，10 万向量检索性能明显劣于 faiss-C++；且引入 `grpcio` 等额外依赖。**P2**：如需服务端/过滤能力再引入 |
| hnswlib | HNSW 算法标杆，内存占用低、召回高 | 被 Voyager/Chroma 等使用 | Apache-2.0 | **差**：PyPI 最新仅 0.8.0（2023-12），且**只有 sdist 无 wheel**；0.9.0 不在 PyPI | **出局**：PyPI 仅提供 sdist，安装必编译 pybind11 扩展 → 本机无 MSVC 必然失败 | **不选。**「维护活跃度」与「免编译可安装性」双否决：PyPI 无 wheel + 无编译器 = 干净环境一键复现不可达 |
| 纯 numpy 内存余弦 | 小数据量（< 5 万 × 384 维）暴力点积约几十 ms；无增量/持久化能力 | 零依赖 | 无（自研） | 自维护 | 免编译（numpy 已有） | **不选为主实现，仅作离线兜底。** 作为 `offline` profile 的 `NumpyVectorIndex`（保证零下载可跑），主实现仍用 faiss |

### 6.2 稠密嵌入

| 候选 | 性能 | 生态 | 许可证 | 维护活跃度 | Win 无 GPU 免编译可安装性 | 结论与理由原文 |
|---|---|---|---|---|---|---|
| **fastembed 0.8.0（ONNX Runtime）** ✅ | ONNX Runtime CPU EP，bge-small-zh-v1.5（512 维/中文）批量嵌入 CPU 上约数百句/秒；无需 torch | Qdrant 官方维护；模型清单含 bge-small-zh / bge-m3 / e5 系列；**已装** | Apache-2.0（库）；模型各自许可（bge 系列 MIT / Apache-2.0） | 高（Qdrant 团队持续迭代，多语言绑定） | 纯 Python + onnxruntime，**本环境已装免编译** | **选它为主实现。** 唯一同时满足「免编译 + 无 torch + CPU 高性能 + 中文模型齐全 + 已实测 import」的方案。**风险**：默认从 HF 下载权重，而 huggingface.co 不可达 → 必须实现 ModelScope 下载通道（P1），离线时降级到 `HashingEmbedder` |
| sentence-transformers（torch） | 与 ONNX 同源模型，CPU 吞吐相近但启动慢、内存占用高 | 生态最大，模型最多 | Apache-2.0 | 高 | torch CPU wheel 体积 ~200MB+，需额外下载；本机 C 盘仅 31G，且 torch 依赖链易触发版本冲突 | **不选。**「免编译可安装性」虽可满足（torch 有官方 win wheel），但体积大、依赖重、与「干净环境一键可复现 + 磁盘紧张」冲突；且 fastembed 已覆盖所需模型 |
| Ollama `/api/embed` | 依赖 Ollama 服务，需常驻进程 + 拉取 GB 级模型；单条延迟含 HTTP 开销 | 生态好，模型多 | MIT（服务端） | 高 | 需额外安装 Ollama 客户端（本机未确认已装），模型 ~1GB | **不选为主，P2 备选。** 引入外部守护进程违反「一键零干预」；仅在用户已装 Ollama 时作为 adapter |
| ModelScope + ONNXRuntime 手工 | 性能等同 fastembed，但需自写 tokenizer 前后处理与模型管理 | ModelScope 中文模型丰富 | 依模型而定 | 中 | 需 `pip install modelscope`（纯 Python 可装）；手工 ORT 推理无编译 | **不选为准方案，作为 fastembed 的**模型获取通道**：用 modelscope 下载 ONNX 权重到本地缓存目录，再交给 fastembed/ORT 加载；避免与 HF 网络耦合 |

### 6.3 稀疏 / 词法检索

| 候选 | 性能 | 生态 | 许可证 | 维护活跃度 | Win 无 GPU 免编译可安装性 | 结论与理由原文 |
|---|---|---|---|---|---|---|
| **rank-bm25 0.2.2** ✅ | 纯 Python，10 万 chunk 级语料单次查询 ~10-100ms（可接受，且可用倒排优化）；支持 Okapi/BM25L/BM25+ | 轻量、被大量教学与生产项目使用；无依赖 | Apache-2.0 | 中（功能稳定，变更少；**稳定即优势**） | 纯 Python，**本环境已装** | **选它。** 算法行为完全确定、可断言（单测可验证 IDF 公式），零安装风险，许可证宽松。**优化**：自实现倒排索引 + 中文 2-gram 分词包在 rank_bm25 之上（属「配置/适配」非「重写算法」） |
| 自写 Robertson IDF BM25 | 同级别 | 无 | — | 自维护 | 免编译 | **不选。** 违反「禁止从零自研」：rank-bm25 已完全满足需求，自写无收益且增加出错面 |
| Whoosh | 纯 Python 全文索引，功能全（高亮/短语）但性能一般 | 曾是 Python 全文检索首选 | BSD-2-Clause | **差**：长期低维护（近 5 年几无实质更新），对新 Python 版本兼容性有风险 | 纯 Python 免编译 | **不选。**「维护活跃度」否决：引入停滞依赖会破坏长期可复现性 |
| tantivy（tantivy-py） | Rust 实现，BM25 性能最好（近 Lucene 级） | Quickwit 生态 | MIT | 高（持续发版，0.26.x） | **风险高**：0.22.2 有 win_amd64 wheel 但**仅覆盖 cp39–cp312，无 cp313**；本机是 Python 3.13 → 极可能触发源码构建需要 Rust 工具链 | **不选为主，P2 备选。** 性能最优但与「Py3.13 + 无工具链 + 一键复现」硬约束冲突；若 P2 阶段实测 `pip install tantivy` 在 cp313 能装到 wheel，可作为可选 backend |

### 6.4 重排（Rerank）

| 候选 | 性能 | 生态 | 许可证 | 维护活跃度 | Win 无 GPU 免编译可安装性 | 结论与理由原文 |
|---|---|---|---|---|---|---|
| **BAAI/bge-reranker-base (ONNX via fastembed)** ✅ | CPU 上 top-50 重排约数百 ms–1s；中文/英文均强（MTEB rerank 榜前列） | fastembed 内置支持（`OnnxTextCrossEncoder`），一键调用 | **MIT**（fastembed 模型清单明确标注） | 高（BAAI + Qdrant 双活跃） | ONNX + ORT，**免编译**；模型 1.04GB 需下载 | **选它（local profile 默认）。** 中文效果好、MIT 许可最宽松、fastembed 原生支持即「复用而非自研」 |
| Xenova/ms-marco-MiniLM-L-6-v2 (ONNX) | 仅 **0.08GB**，CPU 上极快（约 5-10× 快于 bge-base），但以英文为主 | fastembed 内置 | Apache-2.0 | 高 | 免编译 | **选它作为「低资源/快速模式」默认**（C 盘仅 31G，0.08GB 更友好）；与 bge 通过 `Reranker` Protocol 切换，评估两者 nDCG@10 后决定默认 |
| cross-encoder（torch） | 与 ONNX 同源 | sentence-transformers 生态 | Apache-2.0 | 高 | 需 torch，体积大 | **不选。** 与 6.2 同理：引入 torch 与「轻量可复现」目标冲突 |
| 无重排 | — | — | — | — | — | **作为 offline profile 默认**（保证零模型可跑），并在评测中作为**对照基线**证明重排增益 ≥ 10% |
| IDF 加权词法重排 | 几乎零成本 | — | — | 自维护 | 免编译 | **不选为准方案，仅作 offline 兜底打分**（`LexicalReranker`），其存在只为让离线链路「有重排形状」而非真实语义重排，评测中明确标注不参与质量对比 |

### 6.5 LLM 推理

| 候选 | 性能 | 生态 | 许可证 | 维护活跃度 | Win 无 GPU 免编译可安装性 | 结论与理由原文 |
|---|---|---|---|---|---|---|
| **llama-cpp-python 0.3.19（本地 GGUF）** ✅ | llama.cpp CPU 后端，Qwen2.5-3B Q4_K_M 在 16 线程下可达数–十余 tok/s；**注意**：CPU 小量化模型线程数须锁 2–8（过多线程因内存带宽瓶颈反而更慢） | GGUF 生态最大，ModelScope 可下载 GGUF；支持 OpenAI 兼容 server | MIT | 高（llama.cpp 迭代极快） | **本环境已装**（官方无 win wheel，但本环境已有，**禁止重装**） | **选它为 local profile 主实现。** 本地可控、无 API Key、可流式；模型走 ModelScope 下载 `qwen2.5-3b-instruct-q4_k_m.gguf`（~2GB，磁盘可控） |
| Ollama HTTP | 易用，模型管理方便 | 生态好 | MIT | 高 | 需额外安装守护进程 | **P2 备选 adapter**；不作为默认，因破坏「克隆即可跑」 |
| 远端 OpenAI 兼容 API | 质量最高、延迟低 | 生态最大 | — | — | 免编译 | **P2 备选 adapter**；**验收不得依赖它**（无 API Key 的干净环境必须能跑通） |
| **Mock 确定性生成** | 微秒级，输出完全确定 | — | — | 自维护 | 免编译 | **选它为 offline profile 默认 + 全部单测默认实现。** 模板化拼接检索片段，输出可 golden-file 断言；这是「离线可验证性」的支点 |

### 6.6 编排框架（**需书面论证「自研」是否成立**）

| 候选 | 性能 | 生态 | 许可证 | 维护活跃度 | Win 无 GPU 免编译可安装性 | 结论与理由原文 |
|---|---|---|---|---|---|---|
| **自研轻量编排层（~300 行）** ✅ | 零额外开销，全链路耗时可控可埋点 | 无（但底层全部复用开源组件） | 本项目 Apache-2.0 | 自维护（但代码量小） | 免编译（纯 Python + 已有依赖） | **选它，理由见下方「书面论证」** |
| LlamaIndex | 编排开销小 | 生态大，RAG 组件最全 | MIT | 高，但**版本 API 变动频繁**（0.9→0.10→0.12 多次破坏性重构） | 免编译，但默认路径绑 OpenAI/HF | **不选。** 见论证第 2、3 条 |
| LangChain | 抽象层多，调试成本高 | 生态最大 | MIT / Apache-2.0（多包混用） | 高，但**破坏性变更与依赖膨胀**广受诟病 | 免编译 | **不选。** 见论证第 2、3 条 |
| Haystack（deepset） | 好，Pipeline 抽象清晰 | 生态中上 | Apache-2.0 | 高 | 部分组件需 torch；2.x 与 1.x API 不兼容 | **不选。** 见论证第 3 条 |

**自研编排层的书面理由（用户要求「禁止从零自研，除非开源方案确实无法满足需求」）**：

1. **自研范围严格限定为「编排胶水层」，不是自研 RAG 算法**。全部算法与引擎能力均复用开源：检索 = faiss-cpu、嵌入/重排 = fastembed(ONNX Runtime)、词法 = rank-bm25、生成 = llama-cpp-python、服务 = FastAPI。自研代码仅做「按 config 组装 Protocol 实现 + 串联 + 埋点」，预计 ≤ 300 行，且每个 Protocol 都提供至少一个开源实现。
2. **开源框架与「离线/无 Key/可断言」验收标准冲突**。LlamaIndex / LangChain 的默认 `VectorStoreIndex`、`OpenAIEmbeddings` 等路径假设**可访问 HF 或持有 API Key**；本机 huggingface.co 不可达且验收环境无 Key。要用它们跑通，仍需逐个替换成自定义 adapter——替换后框架本身只剩调用链组织，收益趋近于零，反而引入「框架内部隐式网络调用导致离线失败」的不可控风险（违反 P0-3）。
3. **与「依赖锁定、干净环境可复现」冲突**。两者均为高频破坏性变更生态（LlamaIndex 0.9→0.12、LangChain 0.1→0.3 多次 API 重构），锁定版本后文档/示例易失效；且依赖树庞大（pull 入 openai、tiktoken、SQLAlchemy 等数十个传递依赖），显著抬高 `pip check` 冲突面与 C 盘占用。
4. **与「模块独立可验证 + 单一职责」冲突**。这些框架的核心是「高耦合对象图」（index/retriever/engine 互相持有），难以做到「每个模块单独 `pytest` 并通过 dataclass 边界通信」，而这正是本项目 P0-4/P0-8 的硬要求。
5. **可替换性已被设计保证**：编排层只依赖 `Protocol`（`Embedder / VectorIndex / LexicalIndex / Reranker / LLM`），故 P2-2 提供 LlamaIndex adapter 作为「可替换性证明」——若架构师认为仍需接入，可在不改动业务代码的前提下完成。

> 结论：**自研编排层不属于「重复造轮子」，属于「开源方案在本机硬约束（无网/无 Key/免编译/可锁定/可单测）下无法满足需求」的情形**，上述 5 条即为书面理由，写入 `docs/ARCHITECTURE.md`。

### 6.7 服务框架与 API

| 候选 | 性能 | 生态 | 许可证 | 维护活跃度 | Win 无 GPU 免编译可安装性 | 结论与理由原文 |
|---|---|---|---|---|---|---|
| **FastAPI 0.141.1 + uvicorn 0.53.0** ✅ | Starlette/ASGI，原生 async，天然支持 SSE 流式与高并发 | 生态最大，自动生成 OpenAPI；与 pydantic 2.13 无缝 | MIT | 高 | **本环境已装**，纯 Python 免编译 | **选它。** 原生 async + SSE 满足流式需求；pydantic 模型直接充当模块间数据契约（与「接口定义」要求一致）；自动 OpenAPI 省去手写文档 |
| Flask | 同步 WSGI，SSE/并发需额外组件 | 生态大但偏传统 | BSD-3-Clause | 高 | 免编译 | **不选。** 与「流式生成」「async 检索」目标不匹配，需额外引入 gevent/eventlet 增加复杂度 |
| 无框架（仅 CLI/库） | — | — | — | — | — | **部分采用**：CLI（`python -m helios-ai-stack`）与 Python API 是一等公民，`api` 模块只是**可选外壳**，保证「不启服务也能完整验证」（服务于 P0-3 离线可验证） |

---

## 7. 离线可验证性策略（验收支点）

> 目标：**无网络、无 API Key、无模型文件**的干净环境，`pytest` 与 E2E demo 全绿。

| 层次 | 策略 | 落地方式 |
|---|---|---|
| ① 接口抽象 | 所有外部能力经 `Protocol` 定义：`Embedder / VectorIndex / LexicalIndex / Reranker / LLM`；业务代码只依赖 Protocol | `src/core/protocols.py` |
| ② 三档 Profile | `offline`（默认，全 Mock，零下载）/ `local`（真实 ONNX+GGUF，模型走 ModelScope）/ `remote`（远端 API，P2） | `HELIOS_PROFILE` 环境变量 + `--profile` CLI；`configs/profile_*.yaml` |
| ③ 确定性 Mock | `HashingEmbedder`（mmh3 词哈希 → 固定 384 维、L2 归一，同输入必同输出）/ `NumpyVectorIndex` / `LexicalReranker`（IDF 加权）/ `TemplateLLM`（固定模板拼接，含引用标记） | 结果可 golden-file 断言，单测不 flaky |
| ④ 内置语料 | 仓库自带 `data/corpus/*.txt`（≥ 10 篇，中英混合，作者可控）与 `data/gold.jsonl`（≥ 50 条 query-doc 对） | **不下载任何数据集** |
| ⑤ 网络闸门 | `HELIOS_ALLOW_NETWORK=0` 时，任何出网调用抛 `E_*_NET_DISABLED`；`requires_model` 用例在无模型时 **skip 而非 fail** | `pytest -m "not requires_model"` 为 CI 门禁 |
| ⑥ 模型获取与校验 | `local` profile 经 ModelScope 下载到 `models/`，记录 `sha256`；缺失时**降级**到 lexical-only + 模板生成并打印 WARN，**不崩溃** | `scripts/fetch_models.py --source modelscope` |
| ⑦ 一键脚本 | `setup.ps1`：建 venv → `pip install -r requirements.lock.txt --require-hashes` → `pip check` → 冒烟 import → 默认 **不下载模型**；`demo.ps1`：offline E2E（必过）→ 若模型就绪则追加 local E2E | 全流程退出码可判定 |
| ⑧ 基线可复算 | `bench` / `eval` 在 offline 与 local 两档均可跑，结果写入 `benchmarks/baseline.json` 并在 README 出表 | 保证「量化基线」可复核 |

CI 矩阵（GitHub Actions）：`windows-latest × python 3.13`，步骤 = `pip install -r requirements.lock.txt` → `ruff check` → `pytest -m "not requires_model"` → `python -m helios-ai-stack demo --profile offline`。

---

## 8. 明确不做的事（Out of Scope）

| # | 不做的事 | 原因 |
|---|---|---|
| 1 | 模型训练 / fine-tune / LoRA | 需求为「复用开源成果」；无 GPU 也不具备条件 |
| 2 | 自研 ANN 索引算法、自研 BM25 算法、自研 tokenizer | 已有 faiss / rank-bm25 / tokenizers，违反「禁止从零自研」 |
| 3 | GPU / CUDA / 分布式 / 多机部署 | 本机无 NVIDIA GPU |
| 4 | 需要本地编译的任何依赖（hnswlib、faiss-gpu、onnxruntime-gpu、torch 编译版等） | 无 MSVC/cmake |
| 5 | 依赖 huggingface.co 直连下载 | 本机已实测不可达 |
| 6 | 向量数据库服务端部署（Qdrant/Milvus/Weaviate server） | 引入守护进程破坏「一键复现」；local/嵌入模式已够用（P2 可选 Docker） |
| 7 | 前端工程化（Vite/React/MUI/Tailwind/npm 构建链） | 增加 Node 工具链与编译风险；P1 仅需 FastAPI 托管极简静态页 |
| 8 | 用户体系 / 鉴权 / 计费 / 多租户 | 非本需求范围 |
| 9 | 多模态（图片/音频原生理解） | P2 仅做「OCR 后入库」的轻量形态 |
| 10 | Agent 自主规划 / 工具调用编排平台 | 范围过大；仅提供 MCP 工具接口（P1） |
| 11 | 除中/英文外的语种优化 | 语料与模型覆盖有限 |

---

## 9. 待确认问题（需架构师 / 用户拍板）

| # | 问题 | 背景与影响 | 建议（产品经理倾向） | 需谁拍板 |
|---|---|---|---|---|
| Q1 | **默认交付链路走 `offline` 还是 `local`？** | `offline` 100% 可复现但答案是模板生成（"性能对标 SOTA"说服力弱）；`local` 需下载 ~2.5GB 模型（bge-small-zh ONNX ~0.1GB + bge-reranker-base 1.04GB 或 MiniLM 0.08GB + Qwen2.5-3B Q4_K_M ~2GB），C 盘仅 31G，且 ModelScope 可达性未实测 | **双轨**：默认 `offline`（验收用），`local` 作为 `demo --profile local` 追加演示；重排默认用 **MiniLM-L6（0.08GB）** 省磁盘，bge-reranker-base 作为可选 | 架构师 + 用户 |
| Q2 | **ModelScope 下载通道是否可用？** | huggingface.co 不可达，若 ModelScope 也受限，则 `local` profile 无法准备模型 → 只能交付 offline 版本 | 建议架构阶段先做 15 分钟连通性探针：`pip install modelscope`（纯 Python）后试下 50MB 小文件；若不通，改用「模型不入仓库、文档给出手动放置说明 + 自动降级」 | 架构师（先探明） |
| Q3 | **llama-cpp-python 的 GGUF 线程数与模型规格如何取？** | CPU 小模型线程过多会因内存带宽瓶颈变慢（经验值 2–8）；模型 3B vs 1.5B/7B 直接决定延迟与磁盘 | 建议：模型 `Qwen2.5-3B-Instruct Q4_K_M`（中文强、~2GB）；`n_threads = min(8, cpu_count//2)`，用 `bench` 扫 2/4/6/8/16 取最优并写入基线 | 架构师 |
| Q4 | **自研编排层的书面理由是否获认可？** | 用户明确「禁止从零自研」，需确认 §6.6 的 5 条论证足以豁免「~300 行编排胶水层」 | 建议认可，并在 `docs/ARCHITECTURE.md` 显著位置复述该理由 + 开放 P2-2（LlamaIndex adapter）作为可替换性证据 | 用户 |
| Q5 | **是否引入 Docker 作为交付/验证路径？** | 本机有 Docker 29.7.2；Docker 化可绕开 Windows 依赖地狱，但 Windows 容器镜像体积大、与「本机一键脚本」是两条路径 | 建议：主路径保持原生 Windows 脚本；Docker 作为 **P2 加分项**（仅当时间充裕） | 用户 |
| Q6 | **gold 集与「对标方案」如何定义？** | 「性能对标业界 SOTA」需明确对标对象；公开数据集下载可能受限 | 建议：内置自建 gold 集（作者「晨星」编写，仓库内）+ 三组内部对照（BM25-only / dense-only / hybrid+rerank）；公开数据集（BEIR 子集）作为 P2 | 架构师 + 用户 |

---

## 10. 交付物清单（对应验收）

| # | 交付物 | 路径/形态 |
|---|---|---|
| ① | 完整可运行源码（含 tests 与 examples） | `src/helios-ai-stack/**`，每模块 `tests/` + `examples/minimal.py` |
| ② | 版本锁定依赖清单 + 构建配置 | `requirements.lock.txt`（含 sha256）、`pyproject.toml`、`ruff.toml`、`pytest.ini` |
| ③ | 一键脚本 | `scripts/setup.ps1`、`scripts/demo.ps1`、`scripts/fetch_models.py`、`scripts/smoke.py` |
| ④ | 说明文档 | `README.md`（架构/部署/使用/基线表）、`docs/ARCHITECTURE.md`（接口契约+错误码+自研理由）、`docs/DEPENDENCIES.md`（版本+许可证）、`docs/EVALUATION.md`（基线数据） |
| ⑤ | GitHub 仓库 | 署名统一「晨星」，Apache-2.0，含 GitHub Actions CI |
| ⑥ | 性能与质量基线 | `benchmarks/baseline.json` + README 表格 |

---

*文档结束 ｜ 作者：晨星*
