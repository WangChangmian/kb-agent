# 部署指南（kb-agent）

> 本文档记录**实际部署步骤**与**国内网络环境下的避坑经验**（下文多处坑均来自本项目真实排查过程）。

---

## 1. 部署架构

```
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│  应用容器 kb-agent           │        │  Milvus 三件套（docker-compose）   │
│  uvicorn app.main:app       │◀──────▶│  · etcd    元数据                  │
│  (FastAPI + SSE + Agent)    │ 19530  │  · MinIO   对象存储                │
│  端口 8000                   │        │  · Milvus  向量引擎（19530/9091）  │
└─────────────────────────────┘        └──────────────────────────────────┘
         密钥：env_file 注入                     数据：volumes/ 挂载持久化
```

**数据持久化**：Milvus 数据落在项目目录 `volumes/`（`.gitignore` 已排除，绝不入库）。

---

## 2. 环境要求

| 项 | 要求 |
|----|------|
| Python | 3.12+（开发验证于 3.13） |
| Docker Desktop | 必需（用于 Milvus）；仅用 Chroma 后端时可跳过 |
| 内存 | 建议空闲 **4GB+**（Milvus standalone 需要） |
| API Key | DeepSeek（对话）+ 硅基流动（Embedding） |
| 磁盘 | Milvus 镜像约 1.2GB；Docker 镜像建议迁到非系统盘 |

---

## 3. 部署步骤

### 步骤 0：Python 依赖

```bash
pip install -r requirements.txt
# 复现完全一致的环境：
pip install -r requirements.lock.txt
```

### 步骤 1：配置 `.env`

```bash
cp .env.example .env
```

关键项：

```ini
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1

EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=Pro/BAAI/bge-m3

VECTOR_BACKEND=milvus                 # 或 chroma（本地，无需 Docker）
MILVUS_URI=http://127.0.0.1:19530
```

> ⚠️ 配置优先级：**环境变量 / `.env` > 代码默认值**——改参数请改 `.env`。

### 步骤 2：启动 Milvus（三件套）

```bash
docker compose -f docker-compose.milvus.yml up -d
```

### 步骤 3：验证 Milvus 就绪

```bash
docker compose -f docker-compose.milvus.yml ps     # 三个容器应为 Up
curl http://127.0.0.1:9091/healthz                 # 期望输出 OK
```

> 启动日志里出现 `WARN ... async dial failed, wait for retry` 属于**启动期正常重试**；
> 判断标准是 **`/healthz` 返回 OK** + 日志出现 `query node start successfully`。

### 步骤 4：数据入库

```bash
python scripts/seed.py            # 入库 data/sample 下的文档
```

### 步骤 5：启动应用

方式 A（开发）：

```bash
uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs
```

方式 B（容器）：

```bash
docker compose up --build -d
```

### 步骤 6：验证服务

| 检查项 | 地址 / 命令 | 期望 |
|--------|------------|------|
| 健康检查 | `http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| 接口文档 | `http://127.0.0.1:8000/docs` | Swagger UI |
| 前端演示 | `http://127.0.0.1:8000/static/demo.html` | 打字机效果 + 引用来源 |
| RAG 问答 | `POST /chat/stream` | SSE 流式返回 |
| Agent 对话 | `POST /agent/chat` | 调用工具并回答 |

---

## 4. 🕳️ 国内网络避坑指南（本项目真实踩坑记录）

| 现象 | 原因 | 解法 |
|------|------|------|
| `failed to resolve reference docker.io/...` 拉镜像超时 | Docker Hub 国内不通 | 给镜像加加速前缀；**Docker Desktop → Settings → Docker Engine** 配 `registry-mirrors` |
| `403 Forbidden` 拉 `quay.io/...` | `docker.m.daocloud.io` 只代理 Docker Hub | **按源仓库换前缀**：Docker Hub → `docker.m.daocloud.io/`；quay.io → **`quay.m.daocloud.io/`**；gcr.io → `gcr.m.daocloud.io/` |
| `docker.io/minio/minio` 被拒（denied） | 该仓库被加速器拒绝 | **同一软件多仓库**：MinIO 也在 quay.io 发布 → 改用 `quay.m.daocloud.io/minio/minio:...` ✅ |
| 容器内 `pip install` 失败（`from versions: none`） | PyPI 直连不稳 | Dockerfile 内指定国内源：`pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt` |
| HuggingFace 模型下载失败（如需本地模型） | HF 国内不通 | 设 `HF_ENDPOINT=https://hf-mirror.com`；用 `HF_HOME` 把缓存目录改到非系统盘 |
| Docker 镜像占满 C 盘 | 默认存放在系统盘 | Docker Desktop → Resources → Advanced → **Disk image location** 改到数据盘 |

---

## 5. 🔧 常见故障排查

| 报错 / 现象 | 根因 | 解法 |
|------------|------|------|
| `ConnectionNotExistException: should create connection first` | langchain-milvus 的连接别名取自 pymilvus 客户端内部值，传 `uri` 时别名对不上 | 在 `services/vector_store.py` 中**预建立连接**：`connections.connect(alias=..., host=..., port=...)`（本项目已处理） |
| `get_collection_stats` / `num_entities` 显示 0，但检索有结果 | Milvus 统计依赖 **flush / load**，新插入数据尚未计入 | **用 `query` 实测**判断数据是否存在，别只看统计 |
| `pip` 报 `langchain-milvus requires pymilvus<3.0,>=2.5.7, but you have 2.5.4` | 版本区间不满足 | 装到区间内：`pip install "pymilvus==2.5.7"` |
| `Fatal error in launcher: Unable to create process using ...` | exe 启动器内嵌的 python 路径失效（环境被改名/移动） | ① 用 `python -m 工具名`（如 `python -m pytest -v`）② 或 `pip install --force-reinstall <工具>` |
| 换个目录运行就报"文件找不到" | 相对路径依赖当前工作目录（CWD） | 所有路径用 `BASE_DIR`（`config.py`）锚定成绝对路径 |
| 服务里读不到 `.env` | `.env` 加载路径是相对路径 | `SettingsConfigDict(env_file=str(BASE_DIR / ".env"))`（本项目已处理） |
| 容器内 401 / Key 无效 | `.env` 未通过 `env_file` 注入，或 Key 有误 | 检查 `docker-compose.yml` 的 `env_file`，并确认 `.env` 内容 |

---

## 6. 数据管理与重建

```bash
# 重建向量库（Milvus 中删除集合）
python -c "from pymilvus import MilvusClient; c = MilvusClient('http://127.0.0.1:19530'); c.drop_collection('kb_docs')"
python scripts/seed.py

# 重建本地 Chroma（切换 VECTOR_BACKEND=chroma 时）
rmdir /s /q data\chroma      # CMD
# Remove-Item -Recurse -Force data\chroma     # PowerShell

# 停止 / 清理 Milvus（保数据）
docker compose -f docker-compose.milvus.yml down

# 停止并删除数据（谨慎！会清空 volumes/）
docker compose -f docker-compose.milvus.yml down -v
```

---

## 7. 生产化清单（当前为开发部署，上线前需补）

- [ ] **鉴权**：接口目前无认证，需加 API Key / 登录
- [ ] **限流**：防刷（429 未实现）
- [ ] **会话存储**：内存 `dict` → Redis（支持多实例、重启不丢记忆）
- [ ] **连接复用**：`get_vector_store()` 每次新建 Milvus 连接 → 加实例缓存
- [ ] **可观测**：接入 Langfuse / LangSmith 追踪 + 结构化日志 + 指标监控
- [ ] **HTTPS / 反向代理**：Nginx 前置，SSE 需关闭缓冲（`proxy_buffering off`）
- [ ] **Milvus 分离部署**：生产建议 etcd / MinIO / Milvus 独立部署并配置副本与备份
