"""订阅管理页：当前套餐概览 + 套餐切换/订阅。"""
import streamlit as st

from api_client import ApiError, get, handle_api_error, post

st.title("订阅管理")

try:
    sub = get("/billing/me")
    plans = get("/billing/plans")
except ApiError as e:
    handle_api_error(e)
    st.error(f"加载失败：{e}")
    st.stop()

# 当前订阅概览
with st.container(border=True):
    st.subheader("当前订阅")
    c1, c2, c3 = st.columns(3)
    c1.metric("套餐", sub["plan_name"])
    c2.metric("剩余额度", f"{sub['remaining_quota']} 次")
    expires = sub.get("expires_at")
    c3.metric("到期时间", expires[:10] if expires else "长期有效")

# 套餐列表
st.subheader("可订阅套餐")
for plan in plans:
    is_current = plan["tier"] == sub["tier"]
    price = plan["price_cents"]
    price_text = "免费" if price == 0 else f"¥{price / 100:.0f} / 月"
    with st.container(border=True):
        row = st.container(horizontal=True)
        row.write(f"**{plan['name']}**")
        row.write(price_text)
        st.caption(f"{plan['monthly_quota']} 次生成 / 月 · {plan.get('description') or ''}")
        if is_current:
            st.button("当前套餐", disabled=True, key=f"btn_{plan['tier']}")
        else:
            if st.button(f"订阅 {plan['name']}", key=f"sub_{plan['tier']}"):
                try:
                    out = post("/billing/subscribe", {"tier": plan["tier"]})
                    st.success(out["message"])
                    st.rerun()
                except ApiError as e:
                    handle_api_error(e)
                    st.error(f"订阅失败：{e}")
