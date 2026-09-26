# API 速查本（kb-agent 专用）

> 记录项目里用到的**库函数 / 类 / 方法**（不是自定义变量），按模块归类。
> 用法：遇到不懂的名字先来这里查；新学到的随手补进来。

---

## 0. 遇到陌生函数的通用破解法（比背清单更重要）

```python
import inspect
print(type(某个对象))                     # ① 它到底是什么
print(inspect.signature(某个函数))        # ② 它要什么参数
print(某个对象.__doc__)                   # ③ 它的说明
```

**三步走**：`type()` → `inspect.signature()` → `__doc__`。任何库 10 秒内搞清用法。

---

## 1. 消息类型（LangChain 对话积木）

| 名称 | 是什么 | 用法 | 本项目位置 |
|------|--------|------|-----------|
| `SystemMessage` | 系统提示词（角色/规则） | `SystemMessage(content="你是…")` | `services/agent.py` |
| `HumanMessage` | 用户消息 | `HumanMessage(content=question)` | `services/agent.py` |
| `AIMessage` | 模型回复（`invoke()` 返回值） | 一般不手建 | 隐式 |
| `ToolMessage` | **工具执行结果** | `ToolMessage(content=..., tool_call_id=...)` | `services/agent.py` |

> 记忆口诀：**Human** 人说、**AI** 模型说、**System** 系统说、**Tool** 工具说。

---

## 2. 工具（`langchain_core.tools`）

| 名称 | 是什么 | 用法 | 本项目位置 |
|------|--------|------|-----------|
| `@tool` | 装饰器：函数 → 模型可调用的工具 | 加在函数上一行 | `tools/*.py` |
| `@tool(args_schema=X)` | 指定参数校验模型（Pydantic） | `@tool(args_schema=LeaveQueryInput)` | `tools/employee.py` |
| `tool.invoke({...})` | **执行工具**（传参数字典） | `query_leave_balance.invoke({"employee_id": "E1001"})` | `services/agent.py`、`tests/test_tools.py` |
| `tool.name` | 工具名（模型看到的名字） | `{t.name: t for t in ALL_TOOLS}` | `services/agent.py` |
| `tool.description` | 工具说明（**来自 docstring**） | 自动生成 | — |

**要点**：工具的 docstring 就是给模型看的说明书（能力 / 入参 / 适用场景 / 禁止场景）。

---

## 3. 模型的绑定与调用（最常用）

| 名称 | 是什么 | 用法 | 本项目位置 |
|------|--------|------|-----------|
| `bind_tools([...])` | 把工具清单绑给模型 | `get_llm().bind_tools(ALL_TOOLS)` | `services/agent.py` |
| `.invoke(messages)` | 调用模型（同步，等完整结果） | `response = llm.invoke(messages)` | `agent.py`、`retriever.py` |
| `response.content` | 模型的文本回答 | `return response.content` | `agent.py` |
| `response.tool_calls` | 模型的**调用请求**列表 | `[{'name': ..., 'args': {...}, 'id': 'call_xxx'}]` | `agent.py` |
| `.stream({...})` | 流式（同步逐块） | `for chunk in chain.stream(...)` | `services/retriever.py` |
| `.astream({...})` | 流式（**异步**，FastAPI 用） | `async for chunk in chain.astream(...)` | `app/main.py` |
| `chunk.content` | 流式的每一小段文本（**可能为空**） | `if chunk.content:` 过滤空块 | `app/main.py` |
| `.with_structured_output(Schema, method=...)` | 结构化输出 | DeepSeek 需 `method="function_calling"` | 早期实验 |

> ⚠️ **别混淆**：`tool_calls` 是**模型产出**的请求；`ToolMessage` 是**你的代码产出**的结果。

---

## 4. 提示词与链（LCEL）

| 名称 | 是什么 | 用法 | 本项目位置 |
|------|--------|------|-----------|
| `ChatPromptTemplate.from_messages([...])` | 提示词模板（含 `{变量}` 占位） | `("system", "...")`、`("human", "...")` | `services/retriever.py` |
| `\|`（管道） | **LCEL 组合**：模板与模型串成链 | `prompt \| get_llm()` | `services/retriever.py` |
| `chain.invoke({...})` | 执行链并填变量 | `chain.invoke({"context": ..., "question": ...})` | `services/retriever.py` |

---

## 5. 文档与分块

| 名称 | 是什么 | 用法 | 本项目位置 |
|------|--------|------|-----------|
| `TextLoader(path, encoding=)` | 加载文本文件 | `loader.load()` → 文档列表 | `services/ingest.py` |
| `Document` | 文档对象 | `.page_content`（正文）、`.metadata`（元数据） | 全项目 |
| `RecursiveCharacterTextSplitter(...)` | 分块器 | `chunk_size=500, chunk_overlap=50, separators=[...]` | `services/ingest.py` |
| `.split_documents(docs)` | 切分成块 | 返回块列表 | `services/ingest.py` |
| `.add_documents(chunks)` | **写入向量库** | `vs.add_documents(chunks)` | `services/ingest.py` |

---

## 6. 向量库（Chroma / Milvus）

| 名称 | 是什么 | 备注 |
|------|--------|------|
| `Chroma(collection_name=, embedding_function=, persist_directory=)` | 本地向量库 | 单文件库；`collection_metadata={"hnsw:space": "cosine"}` 指定余弦 |
| `Milvus(embedding_function=, collection_name=, connection_args=, index_params=)` | Milvus 向量库 | `index_params={"metric_type": "COSINE", "index_type": "AUTOINDEX"}` |
| `similarity_search_with_relevance_scores(q, k=)` | 检索并返回分数 | 返回 `[(Document, score), ...]`，score 越接近 1 越相关 |
| `similarity_search(q, k=)` | 只返回文档（无分数） | 粗召回场景 |
| `connections.connect(alias=, host=, port=)` | pymilvus 建立连接 | **本项目需预连接**（langchain-milvus 0.2.x 不会自动建） |
| `MilvusClient(uri)` | 新版客户端（诊断/运维用） | `.list_collections()`、`.query()`、`.load_collection()`、`.drop_collection()`、`.get_collection_stats()` |
| `Collection(name)`（pymilvus） | 集合对象 | `.load()`、`.num_entities`（统计受 flush 影响） |

**业务概念对照**：Database → **Collection（=表）** → Partition（分区）→ Entity（=行）。

---

## 7. Web 层（FastAPI）

| 名称 | 是什么 | 用法 | 本项目位置 |
|------|--------|------|-----------|
| `FastAPI()` | 应用对象 | `app = FastAPI()` | `app/main.py` |
| `@app.get` / `@app.post` | 路由装饰器 | `@app.post("/chat/stream")` | `app/main.py` |
| `StreamingResponse(gen(), media_type=)` | **流式响应** | `media_type="text/event-stream"` | `app/main.py` |
| `StaticFiles(directory=)` + `app.mount(...)` | 挂载静态目录 | 让 `/static/demo.html` 可访问 | `app/main.py` |
| `Path(__file__).resolve().parent` | 定位"当前文件所在目录"（CWD 免疫） | 静态目录、`BASE_DIR` | `app/main.py`、`config.py` |
| `BaseModel` | 请求/响应数据结构 | `class ChatRequest(BaseModel)` | `app/main.py` |
| `HTTPException(status_code=...)` | 抛 HTTP 错误 | 如 429 限流（尚未实现） | — |

---

## 8. 配置（pydantic-settings）

| 名称 | 是什么 | 用法 | 本项目位置 |
|------|--------|------|-----------|
| `BaseSettings` | 配置基类（读环境变量/.env） | `class Settings(BaseSettings)` | `config.py` |
| `SettingsConfigDict(env_file=...)` | 指定 .env 路径等 | 用绝对路径（CWD 免疫） | `config.py` |
| `settings` | 全局配置单例 | `settings.milvus_uri` | 全项目 |
| `BASE_DIR` | 项目根目录 | `Path(__file__).resolve().parent` | `config.py` |

---

## 9. 测试（pytest）

| 名称 | 是什么 | 用法 |
|------|--------|------|
| `pytest` | 测试框架 | `python -m pytest -v`（或 `pytest -v`） |
| 命名约定 | 文件 `test_*.py`、函数 `test_*` | 否则不会被收集 |
| `assert` | 断言 | `assert result["remaining"] == 7` |
| `.invoke({...})` | 直接调用工具（**无需 LLM**） | `query_leave_balance.invoke({"employee_id": "E1001"})` |

---

## 10. Python 常用内置 / 标准库

| 名称 | 作用 | 例子 |
|------|------|------|
| `json.dumps(obj, ensure_ascii=False)` | 对象 → JSON 字符串（中文不转义） | ToolMessage / SSE 事件 |
| `re.fullmatch(pattern, s)` | 整串正则匹配 | 工号格式校验 |
| `dict.setdefault(k, default)` | 有则取、无则设 | `_agent_sessions.setdefault(sid, AgentSession())` |
| `isinstance(x, dict)` | 类型判断 | 判断工具结果是否为 error |
| `enumerate(x)` | 编号遍历 | 打分时给候选编号 |
| `zip(a, b)` | 配对 | 文档与分数配对排序 |
| `sorted(x, key=lambda t: t[1], reverse=True)` | 排序 | 精排取 top3 |
| `str.replace(a, b)` | 替换 | 判卷归一化去空格 |

---

## 11. 核心分界线：Agent 里"谁干什么"

| 环节 | 由谁完成 | 代码位置 |
|------|---------|---------|
| 决定要不要调工具、调哪个、传什么参数 | **模型** | `response.tool_calls` |
| 真正执行工具 | **你的代码** | `AgentSession._run_tool()` |
| 把结果回填给模型 | **你的代码** | `ToolMessage(...)` |
| 循环次数上限 / 失败熔断 | **你的代码** | `max_steps` / `fail_count` |
| 综合结果给最终回答 | **模型** | `response.content` |

> 记住这句话：**模型只做决策，执行永远是代码的活**——这就是 Function Calling 的安全边界。
