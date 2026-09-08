"""登录 / 注册页：JWT 认证入口。"""
import streamlit as st

from api_client import ApiError, login, register

st.title("AgentFlow")
st.caption("多智能体协作的营销内容生成：热点检索 → 平台化文案 → 合规质检")

login_tab, reg_tab = st.tabs(["登录", "注册"])

with login_tab:
    with st.form("login_form"):
        email = st.text_input("邮箱", key="login_email", placeholder="you@example.com")
        password = st.text_input("密码", type="password", key="login_password")
        if st.form_submit_button("登录", type="primary", icon=":material/login:"):
            if not email or not password:
                st.warning("请填写邮箱和密码")
            else:
                try:
                    data = login(email, password)
                    st.session_state.token = data["access_token"]
                    st.session_state.user = data["user"]
                    st.rerun()
                except ApiError as e:
                    st.error(str(e))

with reg_tab:
    with st.form("register_form"):
        email = st.text_input("邮箱", key="reg_email", placeholder="you@example.com")
        nickname = st.text_input("昵称（可选）", key="reg_nickname")
        password = st.text_input("密码", type="password", key="reg_password")
        confirm = st.text_input("确认密码", type="password", key="reg_confirm")
        if st.form_submit_button("注册", type="primary", icon=":material/person_add:",
                                key="register_submit"):
            if not email or not password:
                st.warning("请填写邮箱和密码")
            elif len(password) < 6:
                st.warning("密码至少 6 位")
            elif password != confirm:
                st.warning("两次输入的密码不一致")
            else:
                try:
                    data = register(email, password, nickname or None)
                    st.session_state.token = data["access_token"]
                    st.session_state.user = data["user"]
                    st.rerun()
                except ApiError as e:
                    st.error(str(e))
