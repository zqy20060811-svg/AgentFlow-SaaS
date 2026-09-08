"""对外入口：run_pipeline(topic, platform)。

on_event(event, data) 回调让调用方拿到流水线中间步骤：
- Celery 任务传入 Redis 发布函数 -> 实现实时推送（P3）
- 测试脚本传入 print 包装      -> 本地观察
不传则行为与 P2 一致（仅打印日志）。
"""
import logging

from app.agents.graph import pipeline_app
from app.agents.prompts import PLATFORM_STYLES
from app.agents.state import PipelineState

logger = logging.getLogger(__name__)


def run_pipeline(topic: str, platform: str = "xiahs",
                 on_event=None) -> dict:
    """执行完整的多智能体流水线，返回最终产物。

    Args:
        topic: 营销主题，如 "AI无线耳机"
        platform: xiahs / wechat / linkedin / x
        on_event: 可选回调 on_event(event: str, data: dict)，
                  每个 Agent 步骤触发一次（通过 LangGraph
                  configurable 透传给节点）。
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
        "issues": [],
        "rewrite_count": 0,
        "final_content": {},
    }

    config = {"configurable": {"on_event": on_event}} if on_event else None
    final = pipeline_app.invoke(init_state, config=config)

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
