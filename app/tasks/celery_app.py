"""Celery 应用实例。

Broker（任务队列）与 Backend（结果存储）均使用 Redis——
Redis 既当消息队列又当 Pub/Sub，一套基础设施三个用途。
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "agentflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.generation"],  # worker 启动时自动 import 任务模块
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,       # 任务状态含 STARTED，便于排查
    result_expires=3600,           # 结果保留 1 小时
    broker_connection_retry_on_startup=True,
    worker_max_tasks_per_child=10, # 每 10 个任务重启子进程，防内存泄漏
    # Windows 下 prefork 池不可用，启动时需 --pool=solo
)
