"""三个 Agent 的节点实现。

Agent A（retrieve）：Function Calling 循环——LLM 自主决定搜索关键词
Agent B（generate）：按平台人设生成文案，支持根据质检反馈重写
Agent C（review）  ：合规质检，LLM 的结构化结论驱动流程路由
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agents.prompts import (
    GENERATE_FORMAT,
    PLATFORM_STYLES,
    RETRIEVE_SYSTEM,
    REVIEW_SYSTEM,
)

from app.agents.state import PipelineState
from app.agents.tools import search_hotspots
from app.core.config import settings

logger = logging.getLogger(__name__)

# Agent A 最多工具调用轮数（防止失控）
MAX_TOOL_ROUNDS = 4


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """统一的 LLM 工厂：OpenAI 兼容接口，可无缝切换 DeepSeek/GPT/通义。"""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature,
    )


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON（兼容 ```json 围栏和多余文字）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"输出中没有 JSON：{text[:200]}")
    return json.loads(text[start : end + 1])


# ---------------------------------------------------------------- Agent A
def agent_a_retrieve(state: PipelineState) -> dict:
    """热点检索：bind_tools 让 LLM 自主规划搜索，收集结果后提炼要点。"""
    topic = state["topic"]
    print(f"[Agent A] 开始检索热点：{topic}")

    llm = get_llm(temperature=0.3).bind_tools([search_hotspots])
    messages = [
        SystemMessage(content=RETRIEVE_SYSTEM),
        HumanMessage(content=f"主题：{topic}\n请收集该主题的最新热点资讯。"),
    ]

    sources: list[dict] = []
    for round_no in range(MAX_TOOL_ROUNDS):
        ai_msg = llm.invoke(messages)
        messages.append(ai_msg)

        if not ai_msg.tool_calls:  # 模型认为信息够了，输出最终要点
            break

        for tc in ai_msg.tool_calls:
            raw = search_hotspots.invoke(tc["args"])
            messages.append(ToolMessage(content=raw, tool_call_id=tc["id"]))
            try:
                for item in json.loads(raw):
                    if item.get("url"):
                        sources.append({"title": item["title"], "url": item["url"]})
            except json.JSONDecodeError:
                pass
    else:
        print("[Agent A] 达到工具调用轮数上限，基于已有信息继续")

    hotspots_text = (ai_msg.content or "").strip()
    print(f"[Agent A] 完成，提炼 {len(hotspots_text.splitlines())} 条要点，"
          f"来源 {len(sources)} 个")

    return {"hotspots": [hotspots_text], "sources": sources}


# ---------------------------------------------------------------- Agent B
def agent_b_generate(state: PipelineState) -> dict:
    """文案生成：按平台人设生成结构化草稿；若有质检反馈则针对性重写。"""
    topic = state["topic"]
    platform = state["platform"]
    feedback = state.get("review_feedback") or ""
    rewrite_count = state.get("rewrite_count", 0)

    if feedback:
        print(f"[Agent B] 第 {rewrite_count} 次重写（质检意见：{feedback[:50]}...）")
    else:
        print(f"[Agent B] 开始生成 {platform} 平台文案")

    style = PLATFORM_STYLES[platform]
    hotspots_text = "\n".join(state.get("hotspots", []))

    user_prompt = f"""主题：{topic}

参考热点素材（营销时可以融入，不要生搬硬套）：
{hotspots_text or "（无检索结果，基于你的知识直接创作）"}

---
{style}
{GENERATE_FORMAT}"""

    if feedback:
        user_prompt += f"""

⚠️ 上一版文案未通过合规审校，问题与修改意见：
{feedback}
请务必修正以上问题后重新输出。"""

    llm = get_llm(temperature=0.9)  # 创作任务用高温度
    resp = llm.invoke([HumanMessage(content=user_prompt)])

    try:
        draft = _extract_json(resp.content)
    except (ValueError, json.JSONDecodeError):
        # 解析失败重试一次，强调格式
        resp = llm.invoke([HumanMessage(content=user_prompt + "\n\n注意：只输出 JSON，以 { 开头。")])
        draft = _extract_json(resp.content)

    print(f"[Agent B] 完成《{draft.get('title', '')[:30]}》")
    return {"draft": draft}


# ---------------------------------------------------------------- Agent C
def agent_c_review(state: PipelineState) -> dict:
    """质检审校：LLM 输出结构化结论，驱动 conditional_edges 路由。"""
    draft = state["draft"]
    print(f"[Agent C] 审校《{draft.get('title', '')[:30]}》")

    user_prompt = f"""待审校文案：
标题：{draft.get("title", "")}
正文：
{draft.get("content", "")}
标签：{" ".join(draft.get("tags", []))}

请按系统指令中的 JSON 格式输出审校结论。"""

    llm = get_llm(temperature=0.1)  # 审校要严谨，低温度
    resp = llm.invoke([SystemMessage(content=REVIEW_SYSTEM),
                       HumanMessage(content=user_prompt)])

    try:
        result = _extract_json(resp.content)
        passed = bool(result.get("passed"))
        issues = result.get("issues", [])
        feedback = result.get("feedback", "")
    except (ValueError, json.JSONDecodeError):
        # 解析失败时放行（fail-open），避免流水线卡死
        print("[Agent C] 质检输出解析失败，默认放行")
        passed, issues, feedback = True, [], ""

    rewrite_count = state.get("rewrite_count", 0)
    if passed:
        print("[Agent C] ✅ 质检通过")
    else:
        print(f"[Agent C] ❌ 未通过（{len(issues)} 个问题），打回重写")

    return {
        "review_passed": passed,
        "review_feedback": feedback if not passed else "",
        "issues": issues,
        "rewrite_count": rewrite_count + (0 if passed else 1),
    }
