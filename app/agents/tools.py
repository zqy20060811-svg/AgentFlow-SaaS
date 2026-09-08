"""Agent A 的搜索工具。

用 langchain 的 @tool 装饰器包装 Tavily 客户端，
通过 bind_tools 交给 LLM 做 Function Calling——
由模型自主决定搜索什么关键词，而不是代码写死。
"""
import json
import logging

from langchain_core.tools import tool
from tavily import TavilyClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_tavily_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily_client


@tool
def search_hotspots(query: str) -> str:
    """搜索某个主题的最新资讯、热点新闻和行业动态。

    Args:
        query: 具体的搜索关键词，应比主题本身更细分，如 "AI无线耳机 2026 新品发布"
    """
    client = _get_client()
    resp = client.search(query=query, max_results=5, search_depth="basic")
    results = [
        {
            "title": r.get("title", ""),
            "content": (r.get("content") or "")[:300],  # 截断，控制 token
            "url": r.get("url", ""),
        }
        for r in resp.get("results", [])
    ]
    logger.info("[Tool] search_hotspots(%r) -> %d 条结果", query, len(results))
    # 返回 JSON 字符串，方便节点侧解析出 sources
    return json.dumps(results, ensure_ascii=False)
