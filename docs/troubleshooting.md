# 报错排查手册（徒弟专用，卡住先翻这里）

> 原则：**报错信息是程序在帮你定位问题，不是骂你。** 先读最后一行，再往上翻。
> 还解决不了就把「完整报错 + 你执行了什么命令」原样发给师父。

---

## 一、安装与导入类

### 1. `ModuleNotFoundError: No module named 'langchain_xxx'`
**原因**：包没装。
**解决**：`pip install langchain-openai langchain-chroma langchain-text-splitters langchain-community`
装完跑 `python scripts/compat_check.py` 确认。

### 2. `ModuleNotFoundError: No module named 'langchain_community.document_loaders'`
**原因**：LangChain 1.x 在精简 community 包，个别 loader 可能被挪走。
**解决**：我们的 `m1_reference.py` 已内置纯 Python 兜底（`Path.read_text`），不影响项目跑通。

### 3. `pip install chromadb` 报错（要编译/找不到 wheel）
**原因**：Python 版本太新或平台缺依赖。
**解决**：
- 确认 Python ≥3.10 且是 64 位：`python -c "import platform; print(platform.architecture())"`
- 升级 pip：`python -m pip install --upgrade pip`
- 还不行就换 Python 3.12（企业常用版本，兼容性最稳）

### 4. `pydantic_core` 相关报错
**原因**：pydantic 与 pydantic-core 版本不匹配。
**解决**：`pip install --upgrade pydantic pydantic-core`

---

## 二、调用 API 类

### 5. `AuthenticationError` / `401 Unauthorized` / `Incorrect API key`
**原因**：key 没填、填错、或填到了别人的字段。
**解决**：
- 检查 `.env` 是否已复制（`cp .env.example .env`）
- `LLM_API_KEY` 必须是**你自己账号**的 key
- 不要在任何代码里硬编码 key，统一走 `.env`（`config.py` 会自动读）

### 6. DeepSeek 报 `404` / `model not found` / embeddings 相关错误
**原因（经典坑）**：DeepSeek 官方**没有 embeddings 接口**，你把 `EMBEDDING_PROVIDER=openai` 但 key 是 DeepSeek 的。
**解决**：`.env` 里改
```
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_KEY=你的硅基流动key
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
```
或本地方案 `EMBEDDING_PROVIDER=bge`（先 `pip install langchain-huggingface`）。

### 7. `TimeoutError` / 请求超时
**原因**：网络慢或代理问题（科学上网工具会拦截直连）。
**解决**：检查网络；`llm.py` 里 `timeout=60` 已放宽；国内 API 直连即可。

### 8. `ContextWindowExceeded` / 超长输入
**原因**：检索到的内容太多，超过模型上下文。
**解决**：调小 `config.py` 的 `retriever_top_k`（4 → 2），或分块更小。

---

## 三、结构化输出类

### 9. `json.decoder.JSONDecodeError` / `OutputParserException`
**原因**：你手写 `json.loads()` 解析模型输出（模型偶尔输出非标准 JSON）。
**解决（正确姿势）**：永远用 `with_structured_output(PydanticModel)`，别自己 `json.loads`。这就是第一课的核心。

### 10. `ValidationError: ... Field required`
**原因**：模型输出缺字段或类型不对，被 Pydantic 拦住——**这是好事，不是 bug**（带病运行才是灾难）。
**解决**：给字段写更清楚的 `description`，模型就更听话；或把必填改可选（`| None`）。

---

## 四、RAG 检索类

### 11. 回答总是「资料中未找到」或答非所问
排查顺序（80% 是这三个原因）：
1. **没入库**：先跑 `python scripts/seed.py`，确认输出「合计入库 N 块」且 N > 0
2. **阈值太高**：`config.py` 里 `retriever_score_threshold` 从 0.3 调到 0.2，再看
3. **top_k 太小**：`retriever_top_k` 从 4 调到 6

> 排查口诀：**先确认「检索到了没」，再谈「回答得好不好」**。
> 跑 `python eval/run_eval.py --show` 直接看每条问题检索到了什么。

### 12. 检索到的段落和问题不相关
**原因**：embedding 质量或分块策略问题。
**解决**：换更好的 embedding（bge-m3 > bge-small）；调小 `chunk_size`（500 → 300）；M4 用评估集量化对比。

### 13. 入库后重新入库，回答反而变差/重复
**原因**：同一批文档入了几次库，向量库里是重复块。
**解决**：删掉 `data/chroma/` 目录重新 `seed.py`（向量库可随时重建，这也是它不入 git 的原因）。

---

## 五、FastAPI / SSE 类

### 14. `Address already in use` / 端口被占用
**解决**：换端口 `uvicorn app:app --port 8001`，或 `netstat -ano | findstr 8000` 找到进程杀掉。

### 15. 前端 demo.html 一直转圈、收不到字
排查：
1. 后端日志有没有打印 `[stream closed]`？（有 = 服务端逻辑跑完，问题在前端解析）
2. 是不是直接双击打开的 html？（要访问 `http://127.0.0.1:8000/static/demo.html`，不能 file:// 打开）
3. `media_type="text/event-stream"` 有没有写对？

### 16. 中文乱码
**原因**：JSON 里中文被转义。
**解决**：`json.dumps(..., ensure_ascii=False)`（我们的代码都已写）。

---

## 六、Agent / LangGraph 类

### 17. `create_react_agent` 报 DeprecationWarning 或不存在
**原因**：LangGraph v1 改名 `create_agent`。
**解决**：`m3_reference.py` 已内置跨版本兜底（try/except），直接跑即可。

### 18. 模型一直不调用工具 / 乱调工具
**解决**：
- 工具 docstring 写清楚「什么时候该用」（模型靠它判断）
- System prompt 里明确工具的适用场景
- 检查模型是否支持 Function Calling（deepseek-chat 支持；部分小模型不支持）

### 19. `ToolMessage` 报 id 相关错误
**原因**：`tool_call_id` 没对上。
**解决**：`ToolMessage(content=..., tool_call_id=tc["id"])`，id 必须取自 `tc["id"]`。

---

## 七、Docker 类

### 20. `docker: command not found` / Docker Desktop 没起来
**解决**：装 Docker Desktop 并启动（Windows 需开启 WSL2）；确认任务栏小鲸鱼图标在跑。

### 21. `docker compose up` 报 `.env` 缺失
**解决**：先 `cp .env.example .env` 再 `docker compose up`。

### 22. 容器里报 `sk-xxx` 认证失败
**原因**：`.env` 还是模板值。
**解决**：填真实 key 后 `docker compose up --build`（改 .env 后必须重建，因为 env_file 在启动时注入）。

---

## 八、万能排查流程（背下来）

```
1. 看报错最后一行 → 搜关键词（ModuleNotFoundError / TypeError / AuthenticationError...）
2. 谷歌/问师父：报错原文 + 你的环境（Python 版本、langchain 版本）
3. 复现最小化：单独跑一小段代码，确认是「我的代码」还是「环境」问题
4. 改一处 → 重跑 → 对比
```

**最重要的一条：报错不可怕，可怕的是不把报错发给我。** 原样贴过来，最快解决。
