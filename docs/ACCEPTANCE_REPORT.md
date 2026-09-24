# helios-ai-stack 验收报告

> 作者：晨星 · 版本：0.1.0 · 生成日期：2026-09-25
> 仓库：https://github.com/CJX0712/helios-ai-stack （Apache-2.0）

## 0. 结论先行（Verdict）

✅ **验收通过。** 一套可实际运行、可一键复现的端到端 RAG 系统已交付并发布至 GitHub。

- **干净环境复现**：克隆仓库 → `python scripts/install.py` → 全套门禁 + 离线 demo 跑通，零手工干预。
- **CI 全绿**：`windows-latest × Python 3.13` 12 个步骤全部 PASS（含 Lint / 源码卫生 / gitignore 守护 / import smoke / 单测 / 离线 E2E）。
- **署名统一**：代码头、LICENSE、pyproject、commit author 全部为「晨星」。
- **性能基线**：offline 档下 `hybrid_rerank` 主链路 `doc_hit_rate=1.000`、`doc_mrr=0.929`，p50 ≈ 1.8ms。

---

## 1. 交付概览

| 项 | 值 |
|---|---|
| 仓库 | `CJX0712/helios-ai-stack`（public） |
| 主分支 | `main` |
| 最新提交 | `1c6cbcc` |
| 许可证 | Apache-2.0（`LICENSE` 完整文本，Copyright 2026 晨星） |
| Python | 3.13.14（强制锁 `>=3.13,<3.14`） |
| 代码规模 | 98 个文件，源码模块 ~40 个 |
| 测试 | 26 用例（2 skip：LlamaIndex 适配层在缺依赖时 skip 不 fail） |
| CI | GitHub Actions `ci.yml`，`windows-latest × 3.13`，全绿 |

---

## 2. 架构与模块（单一职责 + Protocol 可注入）

分层 L0–L6，每一层只做一件事；跨层调用全部走 `Protocol` 抽象，默认实现为真实现而非 stub。

| 层 | 模块 | 职责 | 关键 Protocol / 接口 |
|---|---|---|---|
| L0 内核 | `core`（types/serde/config/registry/protocols/errors/codes/hashing/net/text/trace/cache） | 契约、错误码、配置、后端注册表 | `BackendSpec`、`HeliosError` |
| L1 能力 | `embed` / `vector` / `lexical` / `rerank` / `llm` | 5 项原子能力，多实现可切换 | `Embedder` / `VectorStore` / `LexicalStore` / `Reranker` / `LLM` |
| L2 数据 | `ingest` / `chunk` | 语料解析、分块 | `IngestService.ingest()` / `Chunker.chunk()` |
| L3 组合 | `fuse` / `cite` | RRF 融合稠密+稀疏、引用生成 | `Fuser.fuse()` / `Citer.cite()` |
| L4 编排 | `pipeline`（orchestrator） | 串起 ingest→…→cite 全链路 | `Pipeline.add_documents()` / `query()` |
| L5 接口 | `cli` / `api` / `compat` | CLI / HTTP / LlamaIndex 兼容适配 | `helios.cli` / FastAPI `/query` |
| L6 评测 | `evalkit` | 独立索引、对照基线、量化指标 | `run_baselines()` |

**设计纪律（已落地）**
- 重包（faiss / onnx / llama-cpp / mcp）一律**惰性导入**，缺失则降级跳过，不阻塞主链路。
- 三档 `profile` 切换：`offline`（默认，零下载零 Key）/ `local`（Ollama + GGUF）/ `remote`（OpenAI 兼容）。
- 错误码体系：`E_<MODULE>_<REASON>`，统一 `HeliosError(code, message, detail)`（`core/codes.py`）。

---

## 3. 工程纪律与门禁（CI 判据，全部 0 error）

| 门禁 | 命令 | 结果 | 说明 |
|---|---|---|---|
| 依赖锁装 | `pip install -r requirements.lock.txt` + `pip install -e . --no-deps` | ✅ | 14 强制依赖（纯 wheel，零编译）+ 包 editable 安装 |
| 依赖健康 | `pip check` | ✅ | 无冲突 |
| Lint | `ruff check .` | ✅ 0 error | 含 SIM105 修复（`contextlib.suppress`） |
| 源码卫生 | `scripts/scan_emoji.py` | ✅ | emoji 0 / 单文件 ≤300 行 / TODO·FIXME 0 |
| gitignore 守护 | `scripts/check_gitignore.py` | ✅ | 13 源码路径不被忽略、8 产物路径被忽略 |
| 导入冒烟 | `import helios; helios.__version__` | ✅ 0.1.0 | 包可被导入 |
| 单测 | `pytest -m "not requires_model"` | ✅ 26 用例（2 skip） | 模块单测 + 离线 E2E |
| 离线 E2E | `python -m helios.cli demo --profile offline` | ✅ exit 0 | 检索→生成→引用 + 计算器路由 |

**跨终端健壮性**：所有打印中文的入口（`scan_emoji`/`check_gitignore`/`verify`/`install`/`run_demo`/`helios.cli`）在启动时强制 `stdout/stderr` 用 UTF-8（`_ensure_utf8()`），并在 CI 设 `PYTHONUTF8=1`，彻底解决 en-US runner（cp1252）打印中文崩溃问题——已用 `PYTHONIOENCODING=cp1252` 模拟复现并验证全绿。

---

## 4. 一键复现流程（验收标准：克隆 → 一键脚本 → demo 跑通，零手工干预）

```bash
# 1) 克隆
git clone https://github.com/CJX0712/helios-ai-stack.git
cd helios-ai-stack

# 2) 创建虚拟环境并一键安装（装依赖 + 装包本体，幂等可复现）
python -m venv .venv && .venv/Scripts/activate      # Windows；Linux/macOS 用 source .venv/bin/activate
python scripts/install.py

# 3) 跑门禁 + 离线 demo（均退出码 0）
python scripts/verify.py                             # 4 项闸门全 [PASS]
python -m helios.cli demo --profile offline          # 端到端生成答案

# 可选：接真实模型
HELIOS_INSTALL_OPTIONAL=1 python scripts/install.py  # 装 faiss/onnx/llama-cpp/mcp 等
python -m helios.cli eval --profile local            # 用真实嵌入重产出基线
```

> 复现验证记录：本机已在**全新克隆目录 + 全新 venv** 实测 `install.py` → 全套门禁 → 离线 demo 全绿；并以 `cp1252` 终端模拟 CI 复跑六道闸门全部 exit 0。

---

## 5. 评测基线对比（offline 档，5 语料 / 7 gold）

头条指标：`doc_hit_rate`（召回命中率）、`doc_mrr`（文档级平均倒数排名）。

| baseline | doc_hit | doc_mrr | recall@5 | ndcg@10 | p50_ms | 解读 |
|---|---|---|---|---|---|---|
| pure_dense（仅 FAISS 稠密） | 1.000 | 0.857 | 1.000 | 0.857 | 0.4 | 稠密单通路，MRR 受限于哈希嵌入语义弱 |
| pure_bm25（仅词法） | 1.000 | 0.929 | 1.000 | 0.929 | 0.1 | 词法在术语查询上 MRR 更高 |
| hybrid_no_rerank | 1.000 | 0.857 | 1.000 | 0.857 | 0.2 | RRF 融合但未重排，近似纯稠密 |
| **hybrid_rerank（默认主链路）** | **1.000** | **0.929** | **1.000** | **0.929** | **1.8** | 稠密+词法 RRF 融合 + rerank，综合最优 |

**结论**：默认主链路 `hybrid_rerank` 在 7 个 gold 问题上 `doc_hit_rate=1.0`、`doc_mrr=0.929`，与纯 BM25 持平、优于纯稠密，验证「混合检索 + 重排」设计有效。延迟全部亚毫秒~毫秒级，满足本地交互。

> 注：offline 档使用**确定性哈希嵌入**（mmh3 + 中文字符 bigram），指标用于回归基线对照，非 SOTA 绝对性能。接入 `local`/`remote` 档真实模型后由 `helios.cli eval` 重新产出语义级基线。

---

## 6. 已知限制（透明披露，无隐藏 TODO）

| # | 限制 | 影响 | 处置 |
|---|---|---|---|
| L1 | offline 嵌入为确定性哈希，非语义向量 | offline 基线仅供回归对照 | 切 `local`/`remote` 用真实模型 |
| L2 | faiss/onnx/llama-cpp/mcp 不在强制锁，需 `HELIOS_INSTALL_OPTIONAL=1` | 重通道不默认安装 | 文档已说明，CI 强制锁不含重包以避免 Windows 编译失败 |
| L3 | 无 GPU，未做 GPU 加速路径 | 吞吐受限单机 | 架构预留 `local` 档 Ollama/GGUF |
| L4 | 评测语料与 gold 规模小（5/7） | 基线统计置信有限 | 可扩展 `data/corpus` + `data/gold` |
| L5 | LlamaIndex 适配层需 `llama-index-core` 才启用 | 默认 skip | 缺依赖测试 skip 不 fail，已验证 |

---

## 7. 署名与合规

- **代码作者头**：每个 `.py` 首行 `# 作者：晨星`。
- **LICENSE**：Apache-2.0 完整文本，Copyright 2026 晨星 (Chen Ming)。
- **pyproject**：`authors = [{ name = "晨星" }]`。
- **Git**：commit author 统一 `晨星 <CJX0712@users.noreply.github.com>`。
- **文档**：README / ARCHITECTURE / PRD / TASKS / 本报告均署名晨星。

---

## 8. 验收清单（勾选）

- ✅ 完整可运行源代码（含测试与示例）
- ✅ 版本锁定依赖清单 + 构建配置（`requirements.lock.txt` / `requirements.lock.optional.txt` / `pyproject.toml`）
- ✅ 说明文档（架构 / 部署 / 使用 / 本验收报告）
- ✅ GitHub 仓库，署名统一「晨星」
- ✅ 干净环境克隆→一键脚本→端到端 demo 跑通，零手工干预
- ✅ 模块单测通过（26 用例，2 skip）
- ✅ 依赖锁定、构建可复现
- ✅ 关键指标有量化基线并与对照方案对比
- ✅ CI 在 `windows-latest × 3.13` 全绿
