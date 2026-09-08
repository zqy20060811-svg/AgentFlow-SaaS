"""Celery 任务：包装多智能体流水线，把每步事件发布到 Redis。"""
import uuid

from app.agents.runner import run_pipeline
from app.services.events import publish_event, TERMINAL_EVENTS
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="generation.run")
def run_generation_task(self, task_id: str, topic: str, platform: str) -> dict:
    """异步执行完整流水线。

    task_id 是我们生成的业务 ID（SSE 频道名），与 Celery 自身的
    task request id 解耦——前端只认业务 task_id。
    """
    def on_event(event: str, data: dict) -> None:
        publish_event(task_id, event, data)

    try:
        publish_event(task_id, "task_started",
                      {"celery_id": self.request.id, "topic": topic,
                       "platform": platform})
        result = run_pipeline(topic, platform, on_event=on_event)
        publish_event(task_id, "pipeline_done", result)
        return result
    except Exception as exc:
        publish_event(task_id, "error", {"message": f"生成失败：{exc}"})
        raise


def submit_generation(topic: str, platform: str) -> str:
    """提交生成任务，返回业务 task_id（供前端订阅 SSE）。"""
    task_id = uuid.uuid4().hex
    run_generation_task.delay(task_id, topic, platform)
    return task_id
