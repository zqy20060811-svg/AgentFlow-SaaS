"""生成接口：额度检查 -> 原子扣减 -> 提交异步任务，秒回 task_id。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.generate import GenerateAccepted, GenerateRequest
from app.services.billing import consume_quota
from app.tasks.generation import submit_generation

router = APIRouter(tags=["generate"])


@router.post("/generate", response_model=GenerateAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_generation(payload: GenerateRequest,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    """提交一次内容生成任务（异步）。

    计费：提交时原子预扣 1 次额度，任务失败自动退还。
    额度不足/未订阅/订阅过期返回 402。
    """
    ok, err = consume_quota(db, current_user.id)
    if not ok:
        raise HTTPException(status_code=402, detail=err)

    task_id = submit_generation(current_user.id, payload.topic, payload.platform)
    return GenerateAccepted(task_id=task_id,
                            stream_url=f"/api/v1/stream/{task_id}")
