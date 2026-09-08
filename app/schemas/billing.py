"""计费相关 Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # 支持从 ORM 对象构造

    tier: str
    name: str
    price_cents: int          # 单位：分（0.01 元）
    monthly_quota: int
    description: Optional[str] = None


class SubscriptionOut(BaseModel):
    tier: str
    plan_name: str
    remaining_quota: int
    expires_at: Optional[datetime] = None   # None = 长期有效
    price_cents: int


class SubscribeRequest(BaseModel):
    tier: str = Field(pattern="^(free|pro|ultra)$")


class SubscribeOut(BaseModel):
    message: str
    subscription: SubscriptionOut
