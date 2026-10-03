from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "InvoiceGuard"
    app_env: str = "development"
    app_version: str = "0.1.0"
    database_url: str
    supabase_url: str = ""
    supabase_service_key: str = ""
    log_level: str = "INFO"
    frontend_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
