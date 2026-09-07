from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AgentFlow-SaaS"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+psycopg://agentflow:agentflow@localhost:5432/agentflow"
    REDIS_URL: str = "redis://localhost:6379/0"

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"

    TAVILY_API_KEY: str = ""

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    class Config:
        env_file = ".env"


settings = Settings()
