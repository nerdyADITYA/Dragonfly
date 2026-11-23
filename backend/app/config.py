from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dragonfly.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_eager: bool = False  # run tasks inline (tests / no-Redis dev)
    artifact_dir: str = "./artifacts"
    cors_origins: list[str] = ["http://localhost:5173"]

    anthropic_api_key: str | None = None
    ai_model: str = "claude-opus-5-5"
    ai_effort: str = "medium"

    # Hostnames of Dragonfly's own services; scans may never target them (SSRF guard).
    blocked_hosts: list[str] = ["api", "worker", "postgres", "redis", "web", "metadata.google.internal"]


settings = Settings()
