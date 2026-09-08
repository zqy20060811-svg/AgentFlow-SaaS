"""P5 前端全流程自动化验证（Streamlit AppTest）。

进程内直跑真实前端代码 + 真实后端 API + 真实 Celery/SSE，
不受浏览器代理环境影响。

运行：.venv\\Scripts\\python.exe tests\\test_frontend.py
"""
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
sys.path.insert(0, str(FRONTEND))

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(FRONTEND / "streamlit_app.py")
EMAIL, PASSWORD = "test@agentflow.com", "123456"


def test_login_flow():
    """登录页：填表提交 → session_state 写入 token 和 user。"""
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception

    # 登录表单（form_submit_button 按 label 定位）
    at.text_input(key="login_email").set_value(EMAIL).run()
    at.text_input(key="login_password").set_value(PASSWORD).run()
    next(b for b in at.button if b.label == "登录").click().run(timeout=60)

    assert not at.exception, f"登录出现异常：{[str(e.value) for e in at.exception]}"
    assert "token" in at.session_state and at.session_state["token"], "登录后应写入 token"
    assert at.session_state["user"]["email"] == EMAIL
    print("[PASS] 登录流程：token 已写入会话状态")


def test_generation_flow():
    """生成页：填主题提交 → SSE 流式渲染 → 最终文案出现。"""
    # 种入登录态（直接调 API 拿真实 token）
    from api_client import login
    data = login(EMAIL, PASSWORD)

    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["token"] = data["access_token"]
    at.session_state["user"] = data["user"]
    at.run()
    assert not at.exception
    # 登录态下默认页是内容生成：gen_topic 表单存在（set_value 不存在会直接报错）
    at.text_input(key="gen_topic")

    at.text_input(key="gen_topic").set_value("便携咖啡机").run()
    next(b for b in at.button if b.label == "开始生成").click().run(timeout=300)  # 流水线 1~3 分钟

    assert not at.exception, f"生成出现异常：{[str(e.value) for e in at.exception]}"
    assert not at.error, f"不应有红色错误：{[e.value for e in at.error]}"
    assert at.success, "应出现成功提示（文案已生成完毕）"
    # Agent 协作时间线至少包含 A/B/C 三个步骤容器
    assert len(at.status) >= 3, f"Agent 步骤容器不足：{len(at.status)}"
    print(f"[PASS] 生成流程：{len(at.status)} 个步骤容器 + 最终文案已渲染")


def test_billing_page():
    """订阅管理页：当前订阅概览 + 三个套餐卡片。"""
    from api_client import login
    data = login(EMAIL, PASSWORD)

    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["token"] = data["access_token"]
    at.session_state["user"] = data["user"]
    at.run()
    at.switch_page("app_pages/billing.py").run(timeout=60)

    assert not at.exception, f"订阅页异常：{[str(e.value) for e in at.exception]}"
    # 概览 metric：套餐 / 剩余额度 / 到期时间
    assert len(at.metric) >= 3, f"应渲染 3 个 metric，实际 {len(at.metric)}"
    # 三个套餐按钮（免费版置灰）+ 侧栏登出按钮
    assert len(at.button) >= 4, f"应有 3 套餐按钮 + 登出，实际 {len(at.button)}"
    print(f"[PASS] 订阅页：{len(at.metric)} 个 metric、{len(at.button)} 个按钮已渲染")


if __name__ == "__main__":
    test_login_flow()
    test_generation_flow()
    test_billing_page()
    print("\n全部前端流程测试通过 ✅")
