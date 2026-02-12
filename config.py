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
    discord_bot_token: str = ""
    discord_user_id: int = 0

    # OpenAI-compatible API (primary)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model_name: str = "gpt-4o"

    # NVIDIA NIM (fallback)
    nvidia_api_key: str = ""
    nvidia_model: str = "meta/llama-3.1-70b-instruct"
    nvidia_vision_model: str = "meta/llama-3.2-90b-vision-instruct"
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

    # Multi-channel notifications (optional)
    ntfy_topic_url: str = ""
    bark_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wx_bot_url: str = ""
    webhook_url: str = ""
    webhook_method: str = "POST"
    webhook_headers: str = "{}"
    webhook_body: str = "{}"
    webhook_content_type: str = "JSON"

    # Account & proxy rotation
    proxy_rotation_enabled: bool = False
    proxy_pool: str = ""
    proxy_rotation_mode: str = "per_task"
    proxy_rotation_retry_limit: int = 2
    proxy_blacklist_ttl: int = 300
    account_rotation_enabled: bool = False
    account_rotation_mode: str = "per_task"
    account_rotation_state_dir: str = "./state"
    account_rotation_retry_limit: int = 2
    account_blacklist_ttl: int = 300

    # Web UI (optional)
    enable_web_ui: bool = False
    web_port: int = 8000
    web_username: str = "admin"
    web_password: str = "admin123"

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
