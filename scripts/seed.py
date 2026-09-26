"""入库脚本：把 data/sample 下的文档灌进向量库。

用法：
    python scripts/seed.py            # 入库 data/sample 全部文档
    python scripts/seed.py 某文档.md  # 只入库指定文档
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ingest import ingest  # 复用参考答案的入库函数

if __name__ == "__main__":
    sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample"

    targets = sys.argv[1:] or [str(f) for f in sample_dir.glob("*.md")]
    total = 0
    for t in targets:
        n = ingest(t)
        total += n
        print(f"  {Path(t).name}: {n} 块")
    print(f"合计入库 {total} 块")
