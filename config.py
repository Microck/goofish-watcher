"""Configuration management via pydantic-settings."""

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
    discord_bot_token: str
    discord_user_id: int

    # NVIDIA NIM
    nvidia_api_key: str
    nvidia_model: str = "meta/llama-3.1-70b-instruct"
    nvidia_endpoint: str = "https://integrate.api.nvidia.com/v1/chat/completions"

    # Goofish
    goofish_cookie: str | None = None
    goofish_cookies_json_path: Path | None = None

    # Database
    database_path: Path = Field(default=Path("./data/goofish.db"))

    # Scanning defaults
    default_interval_minutes: int = 60
    default_ai_threshold: float = 0.7
    max_listings_per_scan: int = 200
    seen_streak_stop: int = 30
    jitter_minutes: int = 5
    dedupe_retention_days: int = 30

    # Logging
    log_level: str = "INFO"

    @property
    def cookies(self) -> str | None:
        """Get cookies from direct string or JSON file."""
        if self.goofish_cookie:
            return self.goofish_cookie
        if self.goofish_cookies_json_path and self.goofish_cookies_json_path.exists():
            import json

            with open(self.goofish_cookies_json_path) as f:
                data = json.load(f)
            # Support both formats: list of cookie dicts or cookie string
            if isinstance(data, list):
                return "; ".join(f"{c['name']}={c['value']}" for c in data)
            if isinstance(data, dict) and "cookie" in data:
                return data["cookie"]
            if isinstance(data, str):
                return data
        return None


settings = Settings()  # type: ignore[call-arg]
