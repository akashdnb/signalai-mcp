from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIGNALAI_", env_file=".env", extra="ignore")

    service_name: str = "signalai-mcp"
    service_version: str = "0.1.0"
    public_url: AnyHttpUrl = "http://localhost:8000/mcp"
    auth_issuer_url: AnyHttpUrl = "https://auth.example.com"
    required_scope: str = "signalai:read"
    capability_base_url: AnyHttpUrl = "http://signalai-server:3000"
    capability_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    service_token: str | None = None
