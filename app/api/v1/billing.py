"""计费接口：套餐列表、当前订阅、订阅/切换套餐。

演示环境不接支付网关，POST /billing/subscribe 直接视为支付成功；
真实产品在此处插入微信/支付宝下单与回调。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Plan, Subscription, User
from app.schemas.billing import (PlanOut, SubscribeOut, SubscribeRequest,
                                 SubscriptionOut)
from app.services.billing import get_subscription, subscribe as subscribe_svc

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    """列出所有可订阅套餐（公开接口）。"""
    plans = db.query(Plan).order_by(Plan.price_cents).all()
    return [PlanOut.model_validate(p) for p in plans]


def _to_sub_out(db: Session, sub: Subscription) -> SubscriptionOut:
    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
    return SubscriptionOut(
        tier=plan.tier,
        plan_name=plan.name,
        remaining_quota=sub.remaining_quota,
        expires_at=sub.expires_at,
        price_cents=plan.price_cents,
    )


@router.get("/me", response_model=SubscriptionOut)
def my_subscription(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """查询当前订阅状态：套餐、剩余额度、到期时间。"""
    sub = get_subscription(db, current_user.id)
    if sub is None:
        raise HTTPException(status_code=404, detail="尚未订阅任何套餐")
    return _to_sub_out(db, sub)


@router.post("/subscribe", response_model=SubscribeOut)
def subscribe_plan(payload: SubscribeRequest,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """订阅/切换/续订套餐（演示环境模拟支付成功）。"""
    try:
        sub = subscribe_svc(db, current_user.id, payload.tier)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return SubscribeOut(
        message=f"已成功订阅【{_to_sub_out(db, sub).plan_name}】，"
                f"额度已重置为 {sub.remaining_quota} 次",
        subscription=_to_sub_out(db, sub),
    )
