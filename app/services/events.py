"""任务事件的发布与订阅。

解决的核心问题：
1. Worker（Celery 进程）里的 Agent 步骤要实时通知到 API 进程的 SSE 连接
   -> 用 Redis Pub/Sub 跨进程转发
2. Pub/Sub 是 fire-and-forget：如果客户端在事件发生后才连接 SSE，会错过事件
   -> 每个事件同时写入 Redis List 作为历史（RPUSH + TTL），
      SSE 端点先回放历史、再订阅增量，用 seq 序号去重
"""
import json
import threading
import time

import redis

from app.core.config import settings

_pool = redis.ConnectionPool.from_url(settings.REDIS_URL)
_local = threading.local()

TERMINAL_EVENTS = ("pipeline_done", "error")
_EVENT_TTL = 3600  # 事件历史保留 1 小时


def get_redis() -> redis.Redis:
    """每个线程一个客户端（redis-py 连接非线程安全）。"""
    if not hasattr(_local, "client"):
        _local.client = redis.Redis(connection_pool=_pool, decode_responses=True)
    return _local.client


def publish_event(task_id: str, event: str, data: dict) -> None:
    """Worker 侧调用：发布一条 Agent 步骤事件。"""
    r = get_redis()
    seq = r.incr(f"task:{task_id}:seq")
    payload = json.dumps(
        {"seq": seq, "event": event, "data": data}, ensure_ascii=False
    )
    pipe = r.pipeline()
    pipe.rpush(f"task:{task_id}:events", payload)
    pipe.expire(f"task:{task_id}:events", _EVENT_TTL)
    pipe.set(f"task:{task_id}:status",
             "done" if event in TERMINAL_EVENTS else "running", ex=_EVENT_TTL)
    pipe.publish(f"task:{task_id}", payload)
    pipe.execute()


def format_sse(payload: dict) -> str:
    """编码为 SSE 协议格式。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_event_stream(task_id: str, poll_timeout: int = 300):
    """API 侧生成器：回放历史 -> 订阅增量 -> 终止事件结束。

    供 StreamingResponse 消费，产出符合 SSE 协议的字符串。
    """
    r = get_redis()
    sent_seq = 0

    # 1. 回放已发生的事件（覆盖"任务先跑、SSE 后连"的竞态）
    history = r.lrange(f"task:{task_id}:events", 0, -1)
    for raw in history:
        payload = json.loads(raw)
        sent_seq = max(sent_seq, payload["seq"])
        yield format_sse(payload)

    # 2. 最后一个历史事件已是终止事件 -> 流结束
    if history and json.loads(history[-1])["event"] in TERMINAL_EVENTS:
        return

    # 3. 订阅增量（Pub/Sub），直到终止事件或超时
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    try:
        pubsub.subscribe(f"task:{task_id}")
        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            try:
                msg = pubsub.get_message(timeout=1.0)
            except redis.ConnectionError:
                yield format_sse({"seq": 0, "event": "error",
                                  "data": {"message": "事件服务连接中断"}})
                return
            if msg is None:
                # 空转兜底：任务可能在订阅前就写完了终止事件
                if r.get(f"task:{task_id}:status") == "done":
                    latest = r.lrange(f"task:{task_id}:events", -1, -1)
                    if latest:
                        payload = json.loads(latest[0])
                        if payload["seq"] > sent_seq:
                            yield format_sse(payload)
                    return
                continue
            payload = json.loads(msg["data"])
            if payload["seq"] <= sent_seq:  # 历史回放已发过
                continue
            sent_seq = payload["seq"]
            yield format_sse(payload)
            if payload["event"] in TERMINAL_EVENTS:
                return
        yield format_sse({"seq": 0, "event": "error",
                          "data": {"message": "推送超时，请刷新查看结果"}})
    finally:
        pubsub.close()
