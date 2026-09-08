"""AgentFlow 前端入口：登录 gating + 多页导航。

未登录 → 只显示登录/注册页
已登录 → 内容生成（默认）+ 订阅管理，侧栏显示用户信息与剩余额度
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import ApiError, get  # noqa: E402

st.set_page_config(
    page_title="AgentFlow · AI 营销内容生成",
    page_icon=":material/auto_awesome:",
    layout="centered",
)

# 统一初始化会话状态
st.session_state.setdefault("token", None)
st.session_state.setdefault("user", None)


def logout() -> None:
    st.session_state.token = None
    st.session_state.user = None


if not st.session_state.token:
    nav = st.navigation([
        st.Page("app_pages/login.py", title="登录 / 注册", icon=":material/login:"),
    ])
    nav.run()
else:
    with st.sidebar:
        user = st.session_state.get("user") or {}
        st.write(f"**{user.get('nickname') or user.get('email', '')}**")
        st.caption(user.get("email", ""))
        try:
            sub = get("/billing/me")
            st.metric("剩余额度", f"{sub['remaining_quota']} 次")
            st.caption(sub["plan_name"])
        except ApiError as e:
            if e.status == 401:
                logout()
                st.rerun()
            else:
                st.caption("订阅信息加载失败")
        st.button("退出登录", icon=":material/logout:", on_click=logout)

    nav = st.navigation([
        st.Page("app_pages/generate.py", title="内容生成",
                icon=":material/edit_note:", default=True),
        st.Page("app_pages/billing.py", title="订阅管理",
                icon=":material/card_membership:"),
    ])
    nav.run()
