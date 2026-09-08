"""生成相关请求/响应模型。"""
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100, examples=["AI无线耳机"])
    platform: str = Field(default="xiahs",
                          pattern="^(xiahs|wechat|linkedin|x)$")


class GenerateAccepted(BaseModel):
    task_id: str
    status: str = "submitted"
    stream_url: str
