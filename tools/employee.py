"""员工数据工具：查询员工年假余额。

真实项目中这里替换为「查 SQL / 调内部 HR 系统 API」；示例用内存字典模拟企业数据库。
"""
import re

from langchain_core.tools import tool
from pydantic import BaseModel, Field

# 模拟员工数据库
_EMPLOYEE_DB = {
    "E1001": {"name": "张三", "total_leave": 10, "used_leave": 3},
    "E1002": {"name": "李四", "total_leave": 5, "used_leave": 0},
}


class LeaveQueryInput(BaseModel):
    employee_id: str = Field(description="员工工号，格式如 E1001")


@tool(args_schema=LeaveQueryInput)
def query_leave_balance(employee_id: str) -> dict:
    """查询指定员工的年假总额、已休天数与剩余天数。

    入参：employee_id 是员工工号，格式为 E + 4 位数字（如 E1001）。
    适用场景：用户明确提到工号，或需要查询某个员工的年假余额 / 已休 / 剩余天数。
    禁止场景：查询公司制度与流程（请改用 search_knowledge_base）；
    用户没有提供工号时，先向用户询问，不要猜测工号。
    """
    # 输入边界校验：格式不对直接返回错误，不抛异常（工具必须"失败也有返回"）
    if not re.fullmatch(r"^E\d{4}$", employee_id):
        return {"error": "工号格式不正确，应为 E + 4 位数字，如 E1001"}

    emp = _EMPLOYEE_DB.get(employee_id)
    if not emp:
        return {"error": f"未找到员工 {employee_id}"}

    return {
        "employee_id": employee_id,
        "name": emp["name"],
        "total_leave": emp["total_leave"],
        "used_leave": emp["used_leave"],
        "remaining": emp["total_leave"] - emp["used_leave"],
    }
