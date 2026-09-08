# AgentFlow-SaaS 统一镜像：api / worker / frontend 三个服务共用，
# 通过 compose 里不同的 command 启动不同进程
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖（利用 Docker 层缓存：代码变更不触发重装）
# 使用清华 PyPI 镜像：海外源在国内服务器构建时经常超时
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 再拷代码
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY frontend ./frontend

EXPOSE 8000 8501
