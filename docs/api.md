# API 文档（kb-agent）

服务默认地址：`http://127.0.0.1:8000`
自动生成的交互式文档（Swagger UI）：`http://127.0.0.1:8000/docs`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat/stream` | RAG 问答：**SSE 流式输出 + 引用来源** |
| POST | `/agent/chat` | Agent 对话：**工具调用 + 会话记忆** |
| GET | `/health` | 健康检查（容器探活用） |
| GET | `/static/demo.html` | 前端演示页（打字机效果 + 引用来源） |

---

## 1. `POST /chat/stream` —— RAG 流式问答

### 请求

`Content-Type: application/json`

```json
{
  "question": "年假满一年可以休几天？"
}
```

### 响应（Server-Sent Events）

`Content-Type: text/event-stream`，逐条推送：

```
data: {"type": "token", "content": "根据"}

data: {"type": "token", "content": "参考资料"}

data: {"type": "token", "content": "，正式员工入职满 1 年后每年享有 5 天带薪年假。"}

data: {"type": "sources", "sources": [{"source": "data/sample/星辰科技员工手册.md", "content": "正式员工入职满 1 年后，每年享有 5 天带薪年假…", "score": 0.612}]}
```

**事件类型说明**：

| `type` | 含义 | 前端处理 |
|--------|------|---------|
| `token` | 正文片段（可能包含空片段，需过滤空串） | 逐块追加到回答区 → 打字机效果 |
| `sources` | **最后一条**：引用来源列表 | 渲染到底部（文件名 + 片段 + 相关度分数） |

> `sources` 为空数组 `[]` 表示本次未检索到相关内容（此时回答会是"资料中未找到"）。

### 客户端要点

> ⚠️ 浏览器原生 `EventSource` **只支持 GET、不能带请求体**——所以本项目前端用 **`fetch` + `ReadableStream`** 手动读取流，并按空行（`\n\n`）切分 SSE 事件。

### curl 测试

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"年假满一年可以休几天？\"}"
```

（`-N` = 关闭缓冲，否则看不到流式效果）

---

## 2. `POST /agent/chat` —— Agent 对话（工具调用 + 记忆）

### 请求

```json
{
  "question": "员工 E1001 的年假还剩几天？公司规定满一年可以休几天？",
  "session_id": "user-123"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `question` | ✅ | 用户问题 |
| `session_id` | ❌ | 会话标识，默认 `"default"`。**同一个 `session_id` = 同一段记忆**，支持"那他的年假呢"这类指代追问 |

### 响应

```json
{
  "answer": "E1001（张三）的年假剩余 7 天；公司规定：入职满 1 年后每年 5 天，满 5 年 10 天，满 10 年 15 天。"
}
```

### 服务内部行为

1. 模型决策是否需要调用工具，输出 `tool_calls`
2. 服务执行工具（**模型不执行代码**）：
   - `query_leave_balance` —— 查员工私有数据（年假余额）
   - `search_knowledge_base` —— 查公司制度（**RAG 即工具**）
3. 工具结果作为 `ToolMessage`（带 `tool_call_id`）回填，模型据此给出最终回答

**生产安全锁**：最大循环 4 轮（防死循环）｜工具连续失败 2 次熔断（防反复横跳）

### curl 测试

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"员工 E1001 的年假还剩几天？\",\"session_id\":\"user-123\"}"
```

---

## 3. `GET /health` —— 健康检查

```json
{"status": "ok"}
```

用途：Docker / K8s 探活，判断服务是否就绪。

---

## 4. 错误码

| 状态码 | 含义 | 常见原因与排查 |
|--------|------|---------------|
| **422** | 请求体校验失败 | 字段名写错（必须叫 `question`）、类型不对。FastAPI 会返回详细字段错误 |
| **500** | 服务端异常 | 依赖不可用：向量库（Milvus 未启动 / 连接失败）、LLM API（Key 无效 / 余额不足）。查看服务终端日志 |
| **404** | 路径不存在 | 检查 URL；`/static/...` 需要静态目录挂载正确 |

---

## 5. 生产化待办（已知缺口）

- [ ] **鉴权**：当前接口无任何认证，任何人可调用（生产必须加 API Key / 登录）
- [ ] **限流**：防止接口被刷（429 尚未实现）
- [ ] **SSE 断线重连**：客户端异常断开后的续传与幂等
- [ ] **会话存储**：当前记忆存在进程内存（`dict`），多实例部署需换成 Redis
