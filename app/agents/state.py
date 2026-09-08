"""多智能体流水线的共享状态定义。

State 是 LangGraph 的核心概念：所有节点共享同一份状态字典，
每个节点只读写自己关心的字段，状态沿图的边流动。
"""
from typing import TypedDict


class PipelineState(TypedDict, total=False):
    # ---- 输入 ----
    topic: str            # 用户给的主题，如 "AI无线耳机"
    platform: str         # 目标平台: xiahs / wechat / linkedin / x

    # ---- Agent A（热点检索）产出 ----
    hotspots: list[str]   # 提炼的热点素材要点
    sources: list[dict]   # 引用来源 [{title, url}]

    # ---- Agent B（文案生成）产出 ----
    draft: dict           # {"title": str, "content": str, "tags": list[str]}

    # ---- Agent C（质检审校）产出 ----
    review_passed: bool   # 质检是否通过
    review_feedback: str  # 不通过时给 Agent B 的修改意见
    issues: list[str]     # 发现的问题列表

    # ---- 流程控制 ----
    rewrite_count: int    # 已重写次数（上限 2 次，防止死循环）

    # ---- 最终输出 ----
    final_content: dict   # 定稿 {"title", "content", "tags", "sources", "review"}
