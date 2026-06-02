from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    n8n_webhook_url: str = Field(default="http://n8n:5678/webhook", alias="N8N_WEBHOOK_URL")
    admin_ids: list[int] = Field(default=[], alias="ADMIN_IDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    bot_internal_host: str = Field(default="0.0.0.0", alias="BOT_INTERNAL_HOST")
    bot_internal_port: int = Field(default=8000, alias="BOT_INTERNAL_PORT")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
