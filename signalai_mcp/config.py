from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIGNALAI_", env_file=".env", extra="ignore")

    service_name: str = "signalai-mcp"
    service_version: str = "0.1.0"
    public_url: AnyHttpUrl = "http://localhost:8000/mcp"
    auth_issuer_url: AnyHttpUrl = "https://auth.example.com"
    auth_introspection_url: AnyHttpUrl | None = None
    auth_client_id: str | None = None
    auth_client_secret: str | None = None
    auth_tokens: str | None = None
    required_scope: str = "signalai:read"  # Backwards-compatible read-scope setting.
    read_scope: str = "signalai:read"
    write_scope: str = "signalai:write"
    capability_base_url: AnyHttpUrl = "http://signalai-server:3000"
    capability_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    service_token: str | None = None
    allowed_hosts: str = "localhost,127.0.0.1"
    allowed_origins: str = "http://localhost:8000"

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


settings = Settings()
