"""生成接口：提交异步任务，秒回 task_id。

P4 计费闭环将在 create_generation 中插入：
额度检查 -> 扣减 remaining_quota -> 提交任务。
"""
from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models.user import User
from app.schemas.generate import GenerateAccepted, GenerateRequest
from app.tasks.generation import submit_generation

router = APIRouter(tags=["generate"])


@router.post("/generate", response_model=GenerateAccepted, status_code=202)
def create_generation(payload: GenerateRequest,
                      current_user: User = Depends(get_current_user)):
    """提交一次内容生成任务（异步）。返回 task_id 用于订阅 SSE。"""
    task_id = submit_generation(payload.topic, payload.platform)
    # TODO(P4): 在此处插入额度检查与扣减
    return GenerateAccepted(task_id=task_id,
                            stream_url=f"/api/v1/stream/{task_id}")
