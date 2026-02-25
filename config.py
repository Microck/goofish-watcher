"""Configuration management via pydantic-settings.

This repo is intentionally kept small: it exists to
- perform QR login to Goofish/Xianyu and export Playwright storage state
- receive ai-goofish-monitor webhooks and forward them as Discord DMs
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Discord
    discord_bot_token: str = ""
    discord_user_id: int = 0

    # Goofish/Xianyu session
    goofish_cookies_json_path: Path = Field(default=Path("./cookies.json"))

    # Webhook receiver (ai-goofish-monitor -> Discord DM)
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8123
    webhook_path: str = "/webhook/ai-goofish-monitor"
    webhook_secret: str = ""

    # Logging
    log_level: str = "INFO"


settings = Settings()  # type: ignore[call-arg]
