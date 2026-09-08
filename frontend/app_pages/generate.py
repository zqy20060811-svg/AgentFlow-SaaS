"""内容生成页：提交任务 + SSE 实时渲染 Agent 协作时间线。

事件 → UI 映射：
- agent_start  → 新开一个 st.status(type="step") 容器（带竖向连接线的步骤）
- tool_call    → 写入当前步骤（检索关键词）
- agent_done   → 当前步骤标记 complete
- review_result→ 通过=绿色步骤；未通过=红色步骤列出问题
- pipeline_done→ 渲染最终文案卡片 + 引用来源 + 下载
"""
import streamlit as st

from api_client import ApiError, handle_api_error, post, stream_sse

PLATFORMS = {
    "小红书": "xiahs",
    "微信公众号": "wechat",
    "LinkedIn": "linkedin",
    "X (Twitter)": "x",
}
AGENT_LABELS = {
    "A": "🔎 Agent A · 热点检索",
    "B": "✍️ Agent B · 文案生成",
    "C": "🛡️ Agent C · 合规质检",
}


def render_stream(task_id: str, topic: str) -> dict | None:
    """消费 SSE 事件流并渲染时间线，返回最终产物（失败为 None）。"""
    result = None
    current = None  # 当前进行中的 st.status 步骤容器
    st.caption(f"任务已受理，主题：{topic}")

    try:
        for payload in stream_sse(f"/stream/{task_id}"):
            ev = payload.get("event")
            d = payload.get("data", {})

            if ev == "agent_start":
                if current is not None:
                    current.update(state="complete")
                if d.get("rewrite"):
                    label = f"✍️ Agent B · 第 {d['rewrite']} 次重写"
                else:
                    label = AGENT_LABELS.get(d.get("agent"), "Agent")
                current = st.status(label, type="step", expanded=True)

            elif ev == "tool_call":
                if current is not None:
                    current.write(f"🔎 检索：{d.get('query', '')}")

            elif ev == "agent_done":
                if current is not None:
                    current.write(d.get("message", ""))
                    current.update(state="complete")

            elif ev == "review_result":
                if current is not None:
                    current.update(state="complete")
                if d.get("passed"):
                    st.status("🛡️ Agent C · 质检通过", type="step",
                              state="complete", expanded=False)
                else:
                    box = st.status("🛡️ Agent C · 质检未通过，打回重写", type="step",
                                    state="error", expanded=True)
                    for issue in d.get("issues", []):
                        box.write(f"**[{issue.get('level', '')}]** {issue.get('content', '')}")
                current = None

            elif ev == "pipeline_done":
                if current is not None:
                    current.update(state="complete")
                result = d

            elif ev == "error":
                if current is not None:
                    current.update(state="error")
                st.error(f"任务失败：{d.get('message', '未知错误')}")
                return None
    except ApiError as e:
        if current is not None:
            current.update(state="error")
        st.error(f"事件流中断：{e}")

    return result


def render_result(result: dict) -> None:
    """渲染最终文案：标题 / 正文 / 标签 / 引用来源 / 下载。"""
    st.divider()
    st.success("文案已生成完毕")

    title = result.get("title", "")
    content = result.get("content", "")
    tags = result.get("tags", [])

    st.subheader(title)
    st.write(content)
    if tags:
        st.write(" ".join(f"`{t}`" for t in tags))

    sources = result.get("sources", [])
    if sources:
        with st.expander(f"引用来源（{len(sources)}）"):
            for s in sources[:10]:
                st.markdown(f"- [{s.get('title', '')[:60]}]({s.get('url', '')})")

    review = result.get("review", {})
    if review.get("passed"):
        st.caption(f"质检通过 · 重写 {review.get('rewrites', 0)} 次")
    else:
        st.caption(f"质检带问题放行（重写 {review.get('rewrites', 0)} 次后达上限）")

    md = f"# {title}\n\n{content}\n\n{' '.join('#' + t for t in tags)}"
    st.download_button("下载文案", md, file_name="文案.md",
                       icon=":material/download:")


# ------------------------------------------------------------------ 页面
st.title("内容生成")
st.caption("三个 Agent 协作：热点检索 → 平台化文案 → 合规质检（不通过自动打回重写）")

with st.form("generate_form", border=True):
    topic = st.text_input("营销主题", key="gen_topic", placeholder="例如：AI无线耳机")
    platform_label = st.segmented_control("目标平台", list(PLATFORMS), default="小红书")
    submitted = st.form_submit_button("开始生成", type="primary",
                                      icon=":material/auto_awesome:",
                                      key="generate_submit")

if submitted:
    if not topic.strip():
        st.warning("请输入营销主题")
        st.stop()
    try:
        accepted = post("/generate",
                         {"topic": topic.strip(), "platform": PLATFORMS[platform_label]},
                         expect=202)
    except ApiError as e:
        handle_api_error(e)  # 401 会在此 rerun 回登录页
        st.error(f"提交失败：{e}")
        st.stop()

    result = render_stream(accepted["task_id"], topic.strip())
    if result:
        render_result(result)
        try:
            from api_client import get
            sub = get("/billing/me")
            st.caption(f"本次消耗 1 次额度，剩余 {sub['remaining_quota']} 次")
        except ApiError:
            pass
