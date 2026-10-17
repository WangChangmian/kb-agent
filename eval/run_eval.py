"""评估脚本（M4）：不依赖 RAGAS，先量化基础指标。

用法：
    python eval/run_eval.py --basic     # 基础评估：检索命中率 + 端到端答案准确率
    python eval/run_eval.py --show      # 打印每条问题的检索结果，人工检查

指标含义（面试要能讲）：
- 检索命中率 Recall@k：答案关键词是否出现在检索命中的段落里（检索质量）
- 端到端准确率：LLM 最终回答是否包含标准答案（生成质量）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.retriever import ask, retrieve
from eval.judge import normalize,check_answer


def load_eval_set() -> list[dict]:
    return json.loads((Path(__file__).parent / "eval_set.json").read_text(encoding="utf-8"))


def run_basic_eval(verbose: bool = True):
    data = load_eval_set()
    retrieval_hits = 0
    answer_hits = 0

    for item in data:
        q = item["question"]
        docs = retrieve(q, k=4)
        context = "\n".join(d.page_content for d in docs)

        # ---- 检索命中：答案关键词在不在检索到的段落里 ----
        if item["not_found"]:
            retrieval_ok = len(docs) == 0          # 刁难题：期望检索不到
        else:
            retrieval_ok = normalize(item["answer_hint"]) in normalize(context)
        retrieval_hits += retrieval_ok

        # ---- 端到端：LLM 回答里有没有标准答案 ----
        answer = ask(q)
        answer_ok = check_answer(answer, item["answer_hint"], item["not_found"])
        answer_hits += answer_ok

        if verbose:
            # 注意：用 √ / × 而不是 ✓ / ✗ —— 后者不在 GBK 字符集里，
            # 一旦输出被重定向或管道捕获（CI、日志），就会 UnicodeEncodeError 崩溃。
            mark_r = "√" if retrieval_ok else "×"
            mark_a = "√" if answer_ok else "×"
            print(f"[检索{mark_r} 回答{mark_a}] {q}")
            if not answer_ok:
                print(f"    标准: {item['answer_hint']!r} | 实际: {answer[:60]!r}")

    n = len(data)
    print(f"\n{'='*50}")
    print(f"检索命中率 Recall@4 : {retrieval_hits}/{n} = {retrieval_hits/n:.0%}")
    print(f"端到端准确率        : {answer_hits}/{n} = {answer_hits/n:.0%}")
    print("提示：指标 < 80% 就去调 chunk_size / top_k / 阈值，调完重跑对比。")


def show_retrieval():
    """打印每条问题的检索命中段落开头，人工检查检索质量。"""
    for item in load_eval_set():
        print(f"\nQ: {item['question']}")
        docs = retrieve(item["question"], k=4)
        if not docs:
            print("  （无命中——注意：如果是刁难题，这是对的；否则是漏检）")
        for d in docs:
            print(f"  - [{d.metadata.get('score')}] {d.page_content[:50]}...")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--basic"
    if mode == "--show":
        show_retrieval()
    else:
        run_basic_eval()
