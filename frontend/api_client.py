"""FastAPI 后端调用封装（前端唯一出口）。

- 普通请求：get/post，JSON 错误转 ApiError（带状态码）
- SSE 流：stream_sse 生成器逐条 yield 解析好的事件 dict
- 401 统一处理：handle_api_error 清登录态并 rerun 回登录页
- 所有请求 trust_env=False：绕过 Windows 系统代理（Clash 7890 会劫持
  localhost 请求返回 502）
"""
import json
import os

import httpx
import streamlit as st

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:9999")
API = f"{BASE_URL}/api/v1"

NO_PROXY = {"trust_env": False}

# SSE 读超时无限（Agent 流水线 1~3 分钟），连接超时 10s
SSE_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)
DEFAULT_TIMEOUT = 15.0


class ApiError(Exception):
    """后端返回的业务错误（detail + HTTP 状态码）。"""

    def __init__(self, detail: str, status: int = 0):
        super().__init__(detail)
        self.status = status


def _headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _raise(resp: httpx.Response) -> None:
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text or f"HTTP {resp.status_code}"
    raise ApiError(str(detail), resp.status_code)


def handle_api_error(e: ApiError) -> None:
    """401 → 清登录态回登录页；其余原样抛给页面显示。"""
    if e.status == 401:
        st.session_state.token = None
        st.session_state.user = None
        st.rerun()
    raise e


def login(email: str, password: str) -> dict:
    try:
        resp = httpx.post(f"{API}/auth/login", json={"email": email, "password": password},
                          timeout=DEFAULT_TIMEOUT, **NO_PROXY)
    except httpx.RequestError as exc:
        raise ApiError(f"无法连接后端服务（{BASE_URL}）：{exc}") from exc
    if resp.status_code != 200:
        _raise(resp)
    return resp.json()


def register(email: str, password: str, nickname: str) -> dict:
    try:
        resp = httpx.post(f"{API}/auth/register",
                          json={"email": email, "password": password, "nickname": nickname},
                          timeout=DEFAULT_TIMEOUT, **NO_PROXY)
    except httpx.RequestError as exc:
        raise ApiError(f"无法连接后端服务（{BASE_URL}）：{exc}") from exc
    if resp.status_code != 201:
        _raise(resp)
    return resp.json()


def get(path: str) -> dict:
    try:
        resp = httpx.get(f"{API}{path}", headers=_headers(), timeout=DEFAULT_TIMEOUT,
                         **NO_PROXY)
    except httpx.RequestError as exc:
        raise ApiError(f"网络错误：{exc}") from exc
    if resp.status_code != 200:
        _raise(resp)
    return resp.json()


def post(path: str, payload: dict, expect: int = 200) -> dict:
    try:
        resp = httpx.post(f"{API}{path}", headers=_headers(), json=payload,
                          timeout=DEFAULT_TIMEOUT, **NO_PROXY)
    except httpx.RequestError as exc:
        raise ApiError(f"网络错误：{exc}") from exc
    if resp.status_code != expect:
        _raise(resp)
    return resp.json()


def stream_sse(path: str):
    """订阅 SSE 事件流，逐条 yield 解析后的 payload dict。"""
    try:
        with httpx.stream("GET", f"{API}{path}", headers=_headers(),
                          timeout=SSE_TIMEOUT, **NO_PROXY) as resp:
            if resp.status_code != 200:
                resp.read()
                _raise(resp)
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    yield json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
    except httpx.RequestError as exc:
        raise ApiError(f"事件流连接中断：{exc}") from exc
