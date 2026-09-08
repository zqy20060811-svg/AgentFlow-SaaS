"""SSE 实时推送：把 Redis 里的任务事件流式转发给前端。

用 StreamingResponse 而非 WebSocket：Agent 步骤是单向推送，
SSE 更轻量，且浏览器 EventSource 原生支持断线重连。
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.deps import get_current_user
from app.models.user import User
from app.services.events import sse_event_stream

router = APIRouter(tags=["generate"])


@router.get("/stream/{task_id}")
def stream_generation(task_id: str,
                      current_user: User = Depends(get_current_user)):
    """订阅指定任务的 Agent 思考步骤事件流（text/event-stream）。"""
    # 校验 task_id 是合法的 32 位 hex，防止任意 key 注入 Redis channel
    try:
        UUID(hex=task_id)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="非法的 task_id")

    return StreamingResponse(
        sse_event_stream(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 反代时禁用缓冲
        },
    )
