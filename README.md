# kb-agent · 企业知识库问答 Agent

> 基于 **RAG（检索增强生成）** 的企业知识库问答服务：把公司文档分块向量化入库，用户提问时先**向量召回 + cross-encoder 精排**选出最相关的段落，再让大模型**只依据这些段落**流式生成回答并附带引用来源。
> 精排后相关性分数可分（相关 0.94 / 无关 0.001），因此能可靠判断"知识库里没有答案"，**直接拒答**而不是硬编。
> 额外提供 **Agent 工具调用**（RAG 即工具 + 私有数据查询）、**评估集量化指标**与**单元测试**，可 Docker 一键部署。

---

## ✨ 功能特性

| 能力 | 说明 |
|------|------|
| 🔍 **RAG 问答** | 文档分块 → 向量化 → 召回 → **rerank 精排** → 阈值判定 → 大模型生成 |
| 🎯 **Rerank 精排** | 向量召回 16 条后用 cross-encoder 精排取前 4 条（相关块 0.94 / 无关块 0.001） |
| ⚡ **SSE 流式输出** | 打字机效果；前端用 `fetch` + `ReadableStream` 逐块解析渲染 |
| 📎 **引用来源** | 回答附带命中的原文片段与相关度分数，可核对、可追溯 |
| 🛡️ **防幻觉（软 + 硬两层）** | Prompt 约束"只依据参考资料回答"；**代码层**：精排后没有达标段落就直接拒答，不给模型编造的机会 |
| 🤖 **Agent 工具调用** | Function Calling 工具集 + 循环上限 + 连续失败熔断（防死循环） |
| 🧠 **多轮记忆** | 会话级上下文累积，支持"那他的年假呢"这类指代 |
| 🔌 **双向量库后端** | **Chroma**（本地零部署）/ **Milvus**（生产级，Docker 三件套），改 `.env` 一行切换 |
| 📊 **评估驱动** | 10 条评估集（9 条问答 + 1 条防幻觉刁难题），**召回率 / 拒答正确率 / 端到端准确率** 三项分开统计 |
| ✅ **单元测试** | pytest 覆盖判卷、工具纯逻辑，秒级反馈 |
| 🐳 **容器化部署** | 应用镜像 + Milvus 编排（etcd + MinIO + Milvus） |

---

## 🏗 系统架构

```mermaid
flowchart LR
    U["前端 demo.html<br/>fetch + ReadableStream"] -->|"POST /chat/stream (SSE)"| API["FastAPI 接口层<br/>app/main.py"]
    API --> SVC["services 业务层"]
    SVC --> RET["retriever.py<br/>召回 + rerank 精排 + Prompt 组装"]
    RET --> VS[("向量库<br/>Chroma / Milvus")]
    SVC --> LLM["LLM API<br/>DeepSeek（OpenAI 兼容）"]
    RET --> EMB["Embedding<br/>硅基流动 bge-m3（1024 维）"]
    RET --> RR["Rerank<br/>bge-reranker-v2-m3（cross-encoder）"]
```

**两条数据流**：

```
【入库阶段 · 离线，一次做好】
data/sample 文档 → 加载 → 分块（.md 按 ## 标题切；.txt 按字符 300/30）→ Embedding → 写入向量库

【问答阶段 · 在线，每次提问】
用户问题 → 向量召回 16 条 → embedding 阈值粗筛(0.2) → rerank 精排取前 4 →
rerank 阈值判定(0.1) ［一条不剩则直接拒答，不调 LLM］→ 拼 Prompt →
LLM 流式生成（逐 token 推送）→ 最后推送引用来源
```

**为什么检索要分两阶段**（实测数据）：

| 指标 | 相关块 | 无关块 | 能否设绝对阈值 |
|------|--------|--------|----------------|
| embedding 相似度 | 0.757 | 0.579（差 0.18） | ❌ 分不开 |
| **rerank 分数** | **0.94** | **0.001**（差 0.94） | ✅ 随便设 |

> cross-encoder 是把"问题 + 文档"**拼在一起**送进模型判断"这段文字能不能回答这个问题"；
> 而 embedding 是各自编码后比方向，只能判断"像不像"。**召回负责别漏，精排负责别错。**

---

## 📁 目录结构

```
kb-agent/
├── app/
│   ├── main.py              # FastAPI 入口：/chat/stream（SSE）、/health、静态挂载
│   └── static/demo.html     # 前端演示页：打字机效果 + 引用来源
├── services/                # 业务层（换向量库/换模型都只改这里）
│   ├── llm.py               # LLM 工厂（全项目唯一创建模型的地方）
│   ├── vector_store.py      # 向量库工厂（chroma | milvus 配置切换）
│   ├── ingest.py            # 文档入库：加载 → 分块 → 向量化 → 写库
│   └── retriever.py         # 召回 + rerank 精排 + Prompt 链 + 流式问答
├── eval/
│   ├── eval_set.json        # 评估集（含防幻觉刁难题）
│   ├── judge.py             # 判卷纯函数（空格归一化，可单测）
│   └── run_eval.py          # 评估脚本：召回率 / 拒答正确率 / 端到端准确率
├── tests/
│   ├── test_judge.py        # 判卷逻辑单测
│   └── test_tools.py        # 工具层单测（不依赖 LLM）
├── scripts/
│   ├── seed.py              # 批量入库脚本
│   └── compat_check.py      # 环境自检（依赖/API 兼容性）
├── data/sample/             # 演示语料（员工手册 + 客服知识库）
├── docs/                    # 架构、面试讲稿、排错手册
├── config.py                # 配置层（pydantic-settings，路径全部绝对化）
├── docker-compose.yml       # 应用服务
├── docker-compose.milvus.yml# Milvus 三件套（etcd + MinIO + Milvus）
├── requirements.txt         # 依赖声明（版本区间）
└── requirements.lock.txt    # 依赖锁定（本机完整快照）
```

---

## 🚀 快速开始

### 0. 环境要求

- Python 3.12+（开发环境：3.13）
- Docker Desktop（用于启动 Milvus；仅用 Chroma 可跳过）
- API Key：**DeepSeek**（对话）+ **硅基流动**（Embedding，提供 OpenAI 兼容的 `Pro/BAAI/bge-m3`）

> 💡 为什么 Embedding 和对话用不同厂商？**DeepSeek 官方不提供 embeddings 接口**——chat 与 embedding 分开选型是行业常规做法。

### 1. 安装依赖

```bash
pip install -r requirements.txt      # 开发
# 或复现完全一致的环境：
pip install -r requirements.lock.txt
```

### 2. 配置 `.env`

```bash
cp .env.example .env
```

填入你的 Key（见下方"配置项说明"）。

### 3. 启动 Milvus（生产级向量库）

```bash
docker compose -f docker-compose.milvus.yml up -d
docker compose -f docker-compose.milvus.yml ps      # 三个容器应为 Up
curl http://127.0.0.1:9091/healthz                  # 期望输出 OK
```

> 国内网络拉镜像失败时，给镜像加 `quay.m.daocloud.io/`（quay 源）或 `docker.m.daocloud.io/`（Docker Hub 源）前缀。

### 4. 文档入库

```bash
python scripts/seed.py               # 入库 data/sample 下的文档
```

预期输出：`knowledge.txt: 22 块`、`星辰科技员工手册.md: 8 块`，**合计 30 块**。

### 5. 启动服务

```bash
uvicorn app.main:app --reload        # 打开 http://127.0.0.1:8000/docs
```

### 6. 验证

- 接口文档：`http://127.0.0.1:8000/docs`
- 前端演示：`http://127.0.0.1:8000/static/demo.html` → 输入"年假满一年可以休几天？"→ 看**打字机效果 + 底部引用来源**
- 健康检查：`http://127.0.0.1:8000/health`

---

## ⚙️ 配置项说明（`.env`）

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` | 对话模型（OpenAI 兼容协议） | `sk-xxx` / `deepseek-chat` / `https://api.deepseek.com/v1` |
| `EMBEDDING_PROVIDER` | embeddings 提供方 | `siliconflow` |
| `EMBEDDING_MODEL` | 向量模型（1024 维） | `Pro/BAAI/bge-m3` |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` | embeddings 凭证与地址 | `sk-xxx` / `https://api.siliconflow.cn/v1` |
| `VECTOR_BACKEND` | **向量库后端切换** | `milvus` 或 `chroma` |
| `MILVUS_URI` | Milvus 服务地址 | `http://127.0.0.1:19530` |
| `RERANK_API_KEY` | rerank 凭证（**留空则复用 `EMBEDDING_API_KEY`**） | 留空即可 |
| `RERANK_URL` / `RERANK_MODEL` | rerank 服务与模型 | `https://api.siliconflow.cn/v1/rerank` / `BAAI/bge-reranker-v2-m3` |
| `RETRIEVER_RECALL_K` | **召回阶段**取几条交给 rerank | `16` |
| `RETRIEVER_TOP_K` | **精排后**最终返回几条 | `4` |
| `RETRIEVER_SCORE_THRESHOLD` | embedding 分数门槛（粗筛） | `0.2` |
| `RERANK_SCORE_THRESHOLD` | **rerank 分数门槛**（低于它就当作"库里没有答案"） | `0.1` |

> ⚠️ **配置优先级**：环境变量 / `.env` > 代码默认值。改参数请改 `.env`（改 `config.py` 的默认值不生效）。

---

## 📊 评估结果

评估集 10 条（9 条知识问答 + 1 条防幻觉刁难题）。**三项指标分开统计**——因为普通题的"命中"是
"检索到了含答案的段落"，刁难题的"命中"是"**正确地一条都没检索到**"，这是**方向相反**的两种能力，
混成一个数会互相掩盖（召回退步可能被拒答满分抵消）。

| 指标 | Chroma（本地） | Milvus（生产级） |
|------|---------------|-----------------|
| 召回率 Recall@4（9 条普通题） | **100%** | **100%** |
| 拒答正确率（1 条刁难题） | **100%** | **100%** |
| 端到端准确率（10 条） | **100%** | **100%** |

> 换向量库（Chroma → Milvus）**上层代码零改动、指标零变化**——分层设计 + 配置驱动的价值兑现。

### 调参记录（评估驱动开发，真实曲线）

| 阶段 | Recall@4 | 做了什么 / 发现了什么 |
|------|----------|----------------------|
| 初版 | 50% | 建评估集跑基线 —— **但这个 50% 是假的** |
| 按 Markdown 标题重新分块 | **10%** | 假象破碎：原来 3 个大块各自混装 4~5 个章节，"块够大总能撞上答案"。切成 8 个主题块后，**露出真实召回水平** |
| 修复 embedding 参数 | **90%** | 定位到 `check_embedding_ctx_length=True` 会用 tiktoken（英文分词器）把中文重切、decode 还原后再嵌入取平均，**把向量算坏**（相关块 0.23 / 无关块 0.67，语义排序颠倒）。关掉后恢复正常 |
| **接入 rerank + 阈值** | **100%** | cross-encoder 精排 + 绝对分数门槛，**系统才真正具备"拒答"能力** |

> **关键认知：指标下降不一定是退步。** 中间那个 10% 才是诚实的数字——它把"块大蒙对"的假象照了出来。
> **如果一个优化让指标掉了，先别急着回滚，它可能在告诉你真相。**

运行评估：

```bash
python eval/run_eval.py --basic     # 指标统计
python eval/run_eval.py --show      # 打印检索命中内容，人工检查
```

---

## 🧪 测试

```bash
python -m pytest -v
```

覆盖内容：判卷逻辑（空格归一化、刁难题判定）、工具层纯逻辑（工号校验、失败返回 `error`）。

> 理念：**每修完一个 bug，就补一条测试**——踩过的坑不踩第二次。

---

## 🐳 Docker 部署

```bash
# 1) 启动依赖（Milvus 三件套）
docker compose -f docker-compose.milvus.yml up -d

# 2) 构建并启动应用
docker compose up --build -d
```

设计要点：**密钥通过 `env_file` 注入（不进镜像）**；向量库数据用 **volume 持久化**（容器重建不丢）。

---

## 🧭 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | **FastAPI** | 原生异步 + Pydantic 校验 + 自动文档，适配流式场景 |
| 流式协议 | **SSE** | LLM 输出是服务器单向推送，SSE 基于 HTTP、简单、可自动重连 |
| 向量库 | **Chroma / Milvus** | 本地开发用 Chroma；生产用 Milvus（分布式、高并发），配置一键切换 |
| 对话模型 | **DeepSeek**（OpenAI 兼容） | 国内直连、成本低、支持 Function Calling |
| 向量模型 | **bge-m3（硅基流动）** | 中文效果好、1024 维、OpenAI 兼容协议 |
| 编排 | **LangChain 1.x** | 组件化（Prompt / Model / VectorStore）+ LCEL 链式组合 |
| 测试 | **pytest** | 纯逻辑单测，秒级反馈 |

---

## ⚠️ 已知问题 & Roadmap

- [ ] **Milvus 连接未复用**：每次 `get_vector_store()` 会新建连接（日志可见），计划给工厂加实例缓存
- [ ] `requirements.lock.txt` 为本机完整环境快照（含开发期实验依赖），可在干净环境重新生成纯净锁文件
- [ ] **服务无鉴权**：生产部署需补 API Key / 登录鉴权
- [ ] 评估集 10 条 → 扩充到 50+ 条，覆盖更多文档类型（当前刁难题只有 1 条，拒答正确率统计意义弱）
- [ ] 补充集成测试（检索、入库链路）
- [ ] rerank 目前依赖云端 API，可加**本地 cross-encoder 兜底**（离线场景）

---

## 📄 License

MIT
