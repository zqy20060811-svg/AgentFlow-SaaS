"""SaaS 计费核心逻辑。

扣减策略：提交任务时原子预扣 1 次，任务失败由 Worker 退还。
并发安全：单条 UPDATE 带 remaining_quota > 0 条件，数据库层保证
同一行不会扣成负数（两个并发请求只有一个能扣成功）。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Plan, Subscription

# 免费档不设过期时间（None = 长期有效），付费档 30 天
SUBSCRIPTION_DAYS = 30


def get_subscription(db: Session, user_id: int) -> Subscription | None:
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def consume_quota(db: Session, user_id: int) -> tuple[bool, str]:
    """原子扣减 1 次额度。返回 (成功?, 失败原因)。

    先做友好检查（未订阅/过期），真正的防线是原子 UPDATE 的 WHERE 条件。
    """
    sub = get_subscription(db, user_id)
    if sub is None:
        return False, "您还没有订阅任何套餐，请先订阅"

    if sub.expires_at is not None and sub.expires_at < datetime.now(timezone.utc):
        return False, "订阅已过期，请重新订阅"

    result = db.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id, Subscription.remaining_quota > 0)
        .values(remaining_quota=Subscription.remaining_quota - 1)
    )
    db.commit()
    if result.rowcount == 0:
        return False, "生成次数已用完，请升级套餐或等待下月刷新"
    return True, ""


def refund_quota(user_id: int) -> None:
    """任务失败退还 1 次额度。Worker 进程调用（自建独立 session）。"""
    db = SessionLocal()
    try:
        db.execute(
            update(Subscription)
            .where(Subscription.user_id == user_id)
            .values(remaining_quota=Subscription.remaining_quota + 1)
        )
        db.commit()
    finally:
        db.close()


def subscribe(db: Session, user_id: int, tier: str) -> Subscription:
    """订阅/切换套餐（演示环境直接视为支付成功）。

    语义：覆盖当前订阅，额度重置为新套餐月配额，有效期 30 天。
    """
    plan = db.query(Plan).filter(Plan.tier == tier).first()
    if plan is None:
        raise ValueError(f"套餐 {tier} 不存在")

    sub = get_subscription(db, user_id)
    expires = datetime.now(timezone.utc) + timedelta(days=SUBSCRIPTION_DAYS)
    if sub is None:
        sub = Subscription(user_id=user_id, plan_id=plan.id)
        db.add(sub)
    sub.plan_id = plan.id
    sub.remaining_quota = plan.monthly_quota
    sub.expires_at = expires
    db.commit()
    db.refresh(sub)
    return sub
