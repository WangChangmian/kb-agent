import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.retriever import retrieve, _build_chain
from services.agent import AgentSession
from pathlib import Path
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")

class ChatRequest(BaseModel):
    question: str

@app.post('/chat/stream')
async def chat_stream(req:ChatRequest):
    async def gen():
        try:
            docs = retrieve(req.question)
            context = "\n\n".join(d.page_content for d in docs)
            chain = _build_chain()
            async for chunk in chain.astream({"context": context, "question": req.question}):
                if chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"

            sources = [{
                "source": d.metadata.get("source", "未知来源"),
                "content": d.page_content[:100],
                "score": d.metadata.get("score", 0.0), }
                for d in docs
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources}, ensure_ascii=False)}\n\n"
        finally:
            print("stream closed")

    return StreamingResponse(gen(), media_type="text/event-stream")

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------- Agent 接口（Function Calling + 会话记忆） ----------------

class AgentRequest(BaseModel):
    question: str
    session_id: str = "default"          # 同一个 session_id = 同一段记忆


_agent_sessions: dict = {}               # 内存会话（生产环境改用 Redis 等外部存储）


@app.post("/agent/chat")
def agent_chat(req: AgentRequest):
    """带工具调用的对话：可查员工数据 + 查知识库，并保留多轮记忆。"""
    session = _agent_sessions.setdefault(req.session_id, AgentSession())
    return {"answer": session.chat(req.question)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)