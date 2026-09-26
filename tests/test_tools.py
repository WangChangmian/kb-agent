"""工具层单元测试：只测工具的纯逻辑，不依赖 LLM（快、稳定）。"""
from tools.employee import query_leave_balance


def test_正常工号返回剩余天数():
    result = query_leave_balance.invoke({"employee_id": "E1001"})
    assert result["name"] == "张三"
    assert result["remaining"] == 7          # 10 - 3


def test_工号格式错误返回error():
    result = query_leave_balance.invoke({"employee_id": "X999"})
    assert "error" in result


def test_不存在的工号返回error():
    result = query_leave_balance.invoke({"employee_id": "E9999"})
    assert "error" in result
