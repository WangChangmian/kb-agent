"""环境兼容性自检：确认你机器上装的 LangChain 1.x 与项目用到的 API 全部可用。

用法：python scripts/compat_check.py
原理：逐条 import / 检查方法，打印 √ 或 ×。
（用 √ / × 而不是 ✓ / ✗：后者不在 GBK 字符集里，输出被重定向时会崩溃）
"""
import importlib


def has(module: str, attr: str | None = None):
    m = importlib.import_module(module)
    return getattr(m, attr) if attr else m


def main():
    print("== 1. 已安装版本 ==")
    for mod in [
        "langchain", "langchain_openai", "langchain_core",
        "langchain_text_splitters", "langchain_community", "langchain_chroma",
        "langgraph", "fastapi", "pydantic", "chromadb",
    ]:
        try:
            m = importlib.import_module(mod)
            print(f"  √ {mod} {getattr(m, '__version__', '?')}")
        except Exception as e:
            print(f"  × {mod} 未安装 -> {e}")

    print("\n== 2. 项目用到的关键 import ==")
    checks = [
        ("ChatOpenAI", lambda: has("langchain_openai", "ChatOpenAI")),
        ("ChatPromptTemplate", lambda: has("langchain_core.prompts", "ChatPromptTemplate")),
        ("HumanMessage / SystemMessage / ToolMessage",
         lambda: (has("langchain_core.messages", "HumanMessage"),
                  has("langchain_core.messages", "SystemMessage"),
                  has("langchain_core.messages", "ToolMessage"))),
        ("tool 装饰器", lambda: has("langchain_core.tools", "tool")),
        ("RecursiveCharacterTextSplitter", lambda: has("langchain_text_splitters", "RecursiveCharacterTextSplitter")),
        ("TextLoader", lambda: has("langchain_community.document_loaders", "TextLoader")),
        ("Chroma", lambda: has("langchain_chroma", "Chroma")),
    ]
    for name, fn in checks:
        try:
            fn()
            print(f"  √{name}")
        except Exception as e:
            print(f"  × {name} -> {type(e).__name__}: {e}")

    print("\n== 3. 方法能力（大版本升级最容易在这断） ==")
    try:
        from langchain_openai import ChatOpenAI
        print(f"  √ ChatOpenAI.with_structured_output 存在: {hasattr(ChatOpenAI, 'with_structured_output')}")
        print(f"  √ ChatOpenAI.bind_tools 存在: {hasattr(ChatOpenAI, 'bind_tools')}")
    except Exception as e:
        print(f"  × ChatOpenAI -> {e}")

    try:
        from langchain_chroma import Chroma
        print(f"  √ Chroma.similarity_search_with_relevance_scores 存在: "
              f"{hasattr(Chroma, 'similarity_search_with_relevance_scores')}")
    except Exception as e:
        print(f"  × Chroma -> {e}")

    try:
        import langgraph.prebuilt as p
        print(f"  √ langgraph.prebuilt.create_agent (v1 新名): {hasattr(p, 'create_agent')}")
        print(f"  √ langgraph.prebuilt.create_react_agent (旧名): {hasattr(p, 'create_react_agent')}")
    except Exception as e:
        print(f"  × langgraph.prebuilt -> {e}")

    print("\n全部 √ 就可以开始")


if __name__ == "__main__":
    main()
