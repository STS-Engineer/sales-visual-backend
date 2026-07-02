"""
Application configuration loaded from environment variables via Pydantic Settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── Application ───────────────────────────────────────────
    APP_NAME: str = "Sales Visual API"
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    SECRET_KEY: str = "change-me-in-production"

    # ─── Server ────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    PUBLIC_APP_URL: str = "http://localhost:8000"

    # ─── Monday.com ────────────────────────────────────────────
    MONDAY_API_TOKEN: str
    MONDAY_BOARD_ID: str = ""
    MONDAY_API_URL: str = "https://api.monday.com/v2"
    DATABASE_URL: str
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_AUTH: bool = True
    EMAIL_FROM: str = ""
    smtp_from: str | None = None
    email_test_override: str | None = None
    AZURE_CONNECTION_STRING: str = ""
    AZURE_BLOB_CONTAINER: str = "sales-visual-files"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
