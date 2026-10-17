"""入库脚本：把 data/sample 下的文档灌进向量库。

用法：
    python scripts/seed.py            # 入库 data/sample 全部文档
    python scripts/seed.py 某文档.md  # 只入库指定文档
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ingest import ingest  # 复用 services/ingest.py 的入库逻辑（单一实现，避免重复）

if __name__ == "__main__":
    sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample"

    # 按后缀筛选：以前只扫 *.md，导致 data/sample/knowledge.txt（12.9 KB 的主语料）
    # 被静默漏掉——命令成功、有输出，但入库量只有应有的 19%。
    # 用 sorted() 保证顺序确定，避免不同机器上入库顺序不同导致排查困难。
    ALLOWED = {".md", ".markdown", ".txt"}
    targets = sys.argv[1:] or [
        str(f) for f in sorted(sample_dir.iterdir())
        if f.is_file() and f.suffix.lower() in ALLOWED
    ]
    if not targets:
        print(f"[WARN] 没有找到任何待入库文档，目录：{sample_dir}")
        raise SystemExit(1)          # 空集不是成功，是异常（否则定时任务会以为一切正常）

    total = 0
    for t in targets:
        n = ingest(t)
        total += n
        print(f"  {Path(t).name}: {n} 块")
    print(f"合计入库 {total} 块")
