from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_mode: str = "demo"
    devin_api_key: str = ""
    devin_org_id: str = ""
    devin_max_acu_limit: int = 10
    github_token: str = ""
    github_webhook_secret: str = ""
    github_owner: str = ""
    github_repo: str = ""
    public_base_url: str = ""
    database_url: str = "sqlite:///data/app.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
