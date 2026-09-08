"""P2 验收测试：直接运行多智能体流水线（不经 API/Celery）。

用法：
    python tests/test_pipeline.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging

logging.disable(logging.WARNING)  # 压掉 httpx 等噪音日志

from app.agents.runner import run_pipeline  # noqa: E402


def show(result: dict):
    print("\n" + "=" * 60)
    print(f"📌 标题：{result['title']}")
    print("-" * 60)
    print(result["content"])
    print("-" * 60)
    print(f"🏷  标签：{' '.join('#' + t for t in result['tags'])}")
    if result["sources"]:
        print("🔗 引用来源：")
        for s in result["sources"][:5]:
            print(f"   - {s['title'][:40]}  {s['url'][:60]}")
    print(f"✅ 质检：{'通过' if result['review']['passed'] else '带问题放行'}"
          f"（重写 {result['review']['rewrites']} 次）")
    print("=" * 60)


if __name__ == "__main__":
    # 支持命令行参数：python tests/test_pipeline.py [主题] [平台]
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI无线耳机"
    platform = sys.argv[2] if len(sys.argv) > 2 else "xiahs"

    result = run_pipeline(topic, platform)
    show(result)
