"""对外入口：run_pipeline(topic, platform)。

P2 阶段直接同步调用即可在本地跑通；
P3 会被 Celery 任务包裹，并把节点日志换成 SSE 事件推送。
"""
import logging

from app.agents.graph import pipeline_app
from app.agents.prompts import PLATFORM_STYLES
from app.agents.state import PipelineState

logger = logging.getLogger(__name__)


def run_pipeline(topic: str, platform: str = "xiahs") -> dict:
    """执行完整的多智能体流水线，返回最终产物。

    Args:
        topic: 营销主题，如 "AI无线耳机"
        platform: xiahs / wechat / linkedin / x

    Returns:
        {"title", "content", "tags", "sources", "review"} 结构的定稿
    """
    if platform not in PLATFORM_STYLES:
        logger.warning("未知平台 %r，回退为 xiahs", platform)
        platform = "xiahs"

    init_state: PipelineState = {
        "topic": topic,
        "platform": platform,
        "hotspots": [],
        "sources": [],
        "draft": {},
        "review_passed": False,
        "review_feedback": "",
        "rewrite_count": 0,
        "final_content": {},
    }

    final = pipeline_app.invoke(init_state)

    draft = final.get("draft", {})
    result = {
        "title": draft.get("title", ""),
        "content": draft.get("content", ""),
        "tags": draft.get("tags", []),
        "sources": final.get("sources", []),
        "review": {
            "passed": final.get("review_passed", False),
            "feedback": final.get("review_feedback", ""),
            "rewrites": final.get("rewrite_count", 0),
        },
    }
    print(f"[Pipeline] 完成：《{result['title']}》 "
          f"质检{'通过' if result['review']['passed'] else '带问题放行'}，"
          f"重写 {result['review']['rewrites']} 次")
    return result
