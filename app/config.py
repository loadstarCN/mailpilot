from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/mailpilot"
    secret_key: str = "change-me"

    host: str = "0.0.0.0"
    port: int = 8000

    worker_concurrency: int = 5
    worker_poll_interval: float = 1.0

    admin_default_username: str = "admin"
    admin_default_password: str = "changeme"

    session_secret_key: str | None = None
    session_max_age: int = 86400

    @property
    def effective_session_secret(self) -> str:
        return self.session_secret_key or self.secret_key

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
