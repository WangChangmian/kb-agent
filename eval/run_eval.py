"""评估脚本：不依赖 RAGAS，先量化基础指标。

用法：
    python eval/run_eval.py --basic     # 跑指标
    python eval/run_eval.py --show      # 打印每条问题的检索结果（含两个分数），人工检查

三类指标（面试重点：为什么必须分开统计）：
- 召回率 Recall@k ：普通题——答案关键词是否出现在检索到的段落里（考察"能找到"）
- 拒答正确率      ：刁难题——系统是否【正确地一条都没检索到】（考察"知道什么时候找不到"）
- 端到端准确率    ：LLM 最终回答是否包含标准答案（考察生成）

⚠️ 召回和拒答是【方向相反】的两种能力：
   普通题的"命中" = 检索到了含答案的段落（期望条数 > 0）
   刁难题的"命中" = 正确地一条都没检索到（期望条数 == 0）
   混在一个"检索命中率"里会互相掩盖——召回退步可能被拒答满分抵消，指标好看但系统变差。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.judge import check_answer, normalize
from services.retriever import ask, retrieve


def load_eval_set() -> list[dict]:
    return json.loads((Path(__file__).parent / "eval_set.json").read_text(encoding="utf-8"))


def run_basic_eval(verbose: bool = True):
    data = load_eval_set()
    normal_hits = normal_total = 0        # 普通题：召回
    reject_hits = reject_total = 0        # 刁难题：拒答
    answer_hits = 0

    for item in data:
        q = item["question"]
        docs = retrieve(q)                # 走配置（召回调大、rerank 精排、rerank 阈值过滤）
        context = "\n".join(d.page_content for d in docs)

        if item["not_found"]:
            # 刁难题考的是"该拒答时是否拒答"
            reject_total += 1
            retrieval_ok = len(docs) == 0
            reject_hits += retrieval_ok
        else:
            # 普通题考的是"该召回时是否召回到"
            normal_total += 1
            retrieval_ok = normalize(item["answer_hint"]) in normalize(context)
            normal_hits += retrieval_ok

        # 端到端：LLM 回答里有没有标准答案
        answer = ask(q)
        answer_ok = check_answer(answer, item["answer_hint"], item["not_found"])
        answer_hits += answer_ok

        if verbose:
            # 用 √ / × 而不是 ✓ / ✗：后者不在 GBK 字符集里，输出被重定向时会崩溃
            mark_r = "√" if retrieval_ok else "×"
            mark_a = "√" if answer_ok else "×"
            print(f"[检索{mark_r} 回答{mark_a}] {q}")
            if not answer_ok:
                print(f"    标准: {item['answer_hint']!r} | 实际: {answer[:60]!r}")

    print(f"\n{'=' * 52}")
    if normal_total:
        print(f"召回率 Recall@{_k()} : {normal_hits}/{normal_total} = {normal_hits / normal_total:.0%}")
    if reject_total:
        print(f"拒答正确率        : {reject_hits}/{reject_total} = {reject_hits / reject_total:.0%}")
    n = len(data)
    print(f"端到端准确率      : {answer_hits}/{n} = {answer_hits / n:.0%}")
    print("提示：先看 --show 里的两个分数，再决定调 recall_k / 阈值 / 分块，调完重跑对比。")


def _k() -> str:
    """指标名里的 k 从配置读，避免和实际 top_k 不一致。"""
    from config import settings
    return str(settings.retriever_top_k)


def show_retrieval():
    """打印每条问题的检索结果（同时显示 embedding 分数和 rerank 分数），人工检查。"""
    for item in load_eval_set():
        print(f"\nQ: {item['question']}")
        docs = retrieve(item["question"])
        if not docs:
            print("  （无命中——如果是刁难题，这是对的；否则是漏检）")
        for d in docs:
            emb = d.metadata.get("score", "-")
            rr = d.metadata.get("rerank_score", "-")
            print(f"  - [embed {emb} | rerank {rr}] {d.page_content[:50]}...")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--basic"
    if mode == "--show":
        show_retrieval()
    else:
        run_basic_eval()
