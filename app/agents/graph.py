"""LangGraph 图编排：A→B→C 主干 + 质检不通过回 B 的条件边。"""
from langgraph.graph import END, StateGraph

from app.agents.nodes import agent_a_retrieve, agent_b_generate, agent_c_review
from app.agents.state import PipelineState

# 重写上限：质检连续打回 2 次后强制放行（带问题上线好过无限烧钱）
MAX_REWRITES = 2


def _route_after_review(state: PipelineState) -> str:
    """条件路由：质检通过 或 重写次数用尽 → 结束；否则回 Agent B。"""
    if state.get("review_passed") or state.get("rewrite_count", 0) >= MAX_REWRITES:
        return "finish"
    return "regenerate"


def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("retrieve", agent_a_retrieve)
    graph.add_node("generate", agent_b_generate)
    graph.add_node("review", agent_c_review)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "review")

    # Agent C 的 LLM 判断决定流程走向——控制权在模型手里
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {"regenerate": "generate", "finish": END},
    )

    return graph.compile()


# 模块级编译一次，全局复用（编译不调 API，无副作用）
pipeline_app = build_graph()
