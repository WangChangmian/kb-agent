"""Agent 服务：规划-执行-反思循环（Function Calling）+ 生产安全锁 + 会话记忆。

三道保障（都是"生产级 Agent"的必备件）：
1. 循环上限 max_steps —— 防止模型无限要工具（死循环）
2. 连续失败熔断 max_failures —— 工具连续返回 error 时终止，避免反复横跳
3. 会话记忆 —— messages 跨轮累积，支持"那他的年假呢"这类指代

流程：用户提问 → 模型决策（要不要调工具）→ 代码执行工具 → 结果回填 → 模型再决策 → … → 最终回答
注意：**模型不执行代码**，它只输出"调用请求"（tool_calls），执行的是我们。
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from services.llm import get_llm
from tools import ALL_TOOLS

SYSTEM_PROMPT = (
    "你是企业助理，可以调用工具帮用户办事。\n"
    "- 查询员工私有数据（年假余额等）→ query_leave_balance\n"
    "- 查询公司制度、流程、规定 → search_knowledge_base\n"
    "需要时先调用工具，拿到结果后综合回答；工具查不到、知识库没有的，要明确说不知道，不要编造。"
)


class AgentSession:
    """一个会话：持有消息历史（短时记忆）+ 两道安全锁。"""

    def __init__(self, max_steps: int = 4, max_failures: int = 2, system_prompt: str = SYSTEM_PROMPT):
        self.llm_with_tools = get_llm().bind_tools(ALL_TOOLS)
        self.messages: list = [SystemMessage(content=system_prompt)]
        self.max_steps = max_steps
        self.max_failures = max_failures

    # ---------- 对外接口 ----------
    def chat(self, question: str) -> str:
        """一个对话回合：内部可能包含多轮工具调用。回答会自动进入记忆。"""
        self.messages.append(HumanMessage(content=question))
        fail_count = 0

        for _step in range(1, self.max_steps + 1):          # 安全锁①：循环上限
            response = self.llm_with_tools.invoke(self.messages)
            self.messages.append(response)                  # 模型输出进记忆

            if not response.tool_calls:                     # 反思：不再要工具 = 完成
                return response.content

            for tool_call in response.tool_calls:
                result = self._run_tool(tool_call["name"], tool_call["args"])

                if isinstance(result, dict) and "error" in result:
                    fail_count += 1
                    if fail_count >= self.max_failures:     # 安全锁②：连续失败熔断
                        return "多次调用工具未能成功，请确认您提供的信息后重试。"
                else:
                    fail_count = 0                          # 成功一次即清零

                self.messages.append(ToolMessage(
                    content=self._to_text(result),
                    tool_call_id=tool_call["id"],           # 必须对上，模型才知道结果属于哪次调用
                ))

        return "多次尝试仍未完成，请换一种问法或提供更多信息。"

    # ---------- 内部工具 ----------
    @staticmethod
    def _run_tool(name: str, args: dict):
        """按名字执行工具（模型只给名字和参数，执行是我们的活）。"""
        tool_map = {t.name: t for t in ALL_TOOLS}
        tool = tool_map.get(name)
        if tool is None:
            return {"error": f"未知工具：{name}"}
        return tool.invoke(args)

    @staticmethod
    def _to_text(result) -> str:
        """工具结果统一转成字符串（ToolMessage 的 content 必须是文本）。"""
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
