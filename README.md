# helios-ai-stack

> 无 GPU / Windows 机器上可**离线一键复现**的模块化端到端 RAG 系统。
> 作者：**晨星** ｜ License：Apache-2.0 ｜ Python 3.13

一套遵循「单一职责 + Protocol 可注入 + 默认真实现」原则的检索增强生成系统：
ingest → chunk → embed → 稠密检索 / 词法检索 → 融合（RRF）→ 重排 → 生成 → 引用溯源，
全链路在 **offline 档（零下载、零 Key）** 即可完整跑通，并复刻业界开源成果（faiss / BM25 / llama-cpp / ONNX / LlamaIndex）作为可切换后端。

---

## 1. 架构概览

分层（L0–L6），每层只经 `core/types.py` 的 frozen dataclass 与 `core/protocols.py` 的 Protocol 通信：

```
core (L0)        契约/配置/错误码/哈希/文本/网络/注册表
  ├─能力层 (L1)   embed · vector · lexical · rerank · llm   —— 每个能力 = Protocol + 多实现
  ├─数据层 (L2)   ingest · chunk
  ├─组合层 (L3)   fuse (RRF) · cite
  ├─编排层 (L4)   pipeline  (把上述装配成可运行链路，含工厂注入与降级链)
  ├─接口层 (L5)   cli · api (FastAPI/SSE) · compat (LlamaIndex adapter)
  └─评测层 (L6)   evalkit  (文档级头条指标 + 四组对照基线)
```

| 模块 | 默认实现（offline） | 可切换增强实现 |
|---|---|---|
| Embedder | `HashingEmbedder`（确定性哈希，dim=384） | Ollama / ONNX / fastembed |
| VectorIndex | `NumpyVectorIndex`（cosine） | `FaissVectorIndex`（IndexFlatIP） |
| LexicalIndex | `Bm25Index`（Robertson IDF） | `InvertedIndex`（TF-IDF） |
| Reranker | `LexicalReranker`（Jaccard） | `OnnxReranker` / `RemoteReranker` / `NoopReranker`(B0) |
| LLM | `TemplateLLM`（抽取式 + 计算器路由） | Ollama / llama.cpp(GGUF) / OpenAI 兼容 |
| Fusion | `reciprocal_rank_fusion`（RRF, k=60） | —— |

**三档 profile**（`HELIOS_PROFILE`）：`offline`（默认，零下载）→ `local`（本机 Ollama/GGUF 真实模型）→ `remote`（OpenAI 兼容）。换实现只改环境变量，业务代码零改动。

---

## 2. 一键安装与复现

```bash
# 1) 创建隔离环境（Python 3.13）
python -m venv .venv && .venv\Scripts\activate

# 2) 安装强制依赖（干净环境必装，零下载零编译）
python -m pip install -r requirements.lock.txt

# 3) 可编辑安装本项目
python -m pip install -e . --no-deps

# 4) 离线端到端 demo（零下载，必过）
python -m helios.cli demo --profile offline
```

> 可选通道（faiss / onnx / llama-cpp / mcp / LlamaIndex）见 `requirements.lock.optional.txt`，
> 缺则经 registry 降级链自动跳过，**不影响离线 E2E**。需安装时：
> `HELIOS_INSTALL_OPTIONAL=1 python scripts/install.py`

---

## 3. 使用

```bash
# CLI
python -m helios.cli ingest  data/corpus --profile offline
python -m helios.cli query   "什么是 RAG 检索增强生成？" --profile offline
python -m helios.cli eval    --corpus data/corpus --gold data/gold/gold.json
python -m helios.cli serve   --profile offline --port 8000

# HTTP API（FastAPI）
#   GET  /health        POST /ingest        POST /query
uvicorn 启动见 cli serve；/query 返回 Answer(含 citations) 的 JSON。

# 编程接口
from helios.core.config import ProfileConfig
from helios.pipeline import Pipeline
pipe = Pipeline(ProfileConfig.from_env({"HELIOS_PROFILE": "offline"}))
pipe.add_documents([("RAG 通过检索降低幻觉。", "rag.md")])
ans = pipe.query("RAG 是什么？")   # ans.text / ans.citations / ans.timings
```

---

## 4. 评测基线（offline，5 篇语料 / 7 条 gold，文档级头条指标）

| baseline | doc_hit_rate | doc_mrr | recall@5 | recall@10 | ndcg@10 | p50(ms) | p95(ms) |
|---|---|---|---|---|---|---|---|
| pure_dense | 1.000 | 0.857 | 1.000 | 1.000 | 0.857 | 0.2 | 0.3 |
| pure_bm25 | 1.000 | 0.929 | 1.000 | 1.000 | 0.929 | 0.2 | 0.2 |
| hybrid_no_rerank (B0) | 1.000 | 0.857 | 1.000 | 1.000 | 0.857 | 0.2 | 0.2 |
| **hybrid_rerank（默认主链路）** | **1.000** | **0.929** | **1.000** | **1.000** | **0.929** | 1.6 | 2.0 |

> 结论：在离线小语料上，**混合检索 + 重排**相较纯稠密/无重排在 doc_mrr / ndcg@10 上提升约 +0.07，
> 且文档命中率 100%。重排带来约 1.4ms 的额外延迟（p95），属可接受开销。
> 注：offline 档为确定性哈希嵌入，指标用于**回归基线对照**，非 SOTA 绝对性能；接入 local/remote 档真实模型后由 `helios.cli eval` 重新产出。

---

## 5. 工程纪律与验收

- **依赖锁定**：`requirements.lock.txt`（强制）+ `requirements.lock.optional.txt`（可选），版本钉死、`--no-deps` 可复现。
- **源码门禁**（CI 在 `windows-latest × Python 3.13` 全绿）：
  1. `pip install -r requirements.lock.txt` → `pip check`
  2. `ruff check .`（0 error）
  3. `scripts/scan_emoji.py`（emoji 0 / 单文件 ≤300 行 / 遗留待办 0）
  4. `scripts/check_gitignore.py`（源码不被误忽略）
  5. `pytest -m "not requires_model"`（全绿）
  6. `python -m helios.cli demo --profile offline`（端到端 exit 0）
- **错误码体系**：`E_<MODULE>_<REASON>`，统一 `HeliosError(code, message, detail)`（`core/codes.py`）。
- **可替换性证明**：`src/helios/compat/llamaindex_adapter.py` 用 LlamaIndex 实现 3 个能力 Protocol；
  缺 `llama-index-core` 时测试 `skip` 不 fail。

---

## 6. 目录结构

```
src/helios/        # 全部源码（core/ ingest/ chunk/ embed/ vector/ lexical/ fuse/ cite/
                   #         rerank/ llm/ tools/ pipeline/ api/ cli/ evalkit/ compat/）
configs/           # default / profile_{offline,local,remote}.yaml
data/corpus/       # 评测语料（5 篇，中英混合，长度非均匀）
data/gold/gold.json# 文档级 gold 真值（7 条）
scripts/           # install / run_demo / verify / gen_lock / scan_emoji / check_gitignore
docs/              # ARCHITECTURE.md（详细架构）/ PRD.md / TASKS.md（任务分解）
tests/             # 端到端 + 后端 + 工具 + 评测测试
.github/workflows/ # ci.yml（门禁）/ release.yml（发版）
```

---

## 7. 已知限制

- offline 档用确定性哈希嵌入，**不具语义相似度**，仅作可复现基线；真实检索需 local/remote 档嵌入模型。
- faiss / onnx / llama-cpp / LlamaIndex 等增强后端需本机有对应 wheel 或编译工具链（见可选依赖锁）。
- 评测语料为内置小集，用于回归对照；大规模 BEIR 子集对比未进 P0 验收链。

---

*作者：晨星 ｜ 项目名：helios-ai-stack ｜ 包名：helios*
