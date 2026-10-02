from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://hive:hivepass@localhost:5432/hive"
    # Migrations connect to Postgres directly, bypassing PgBouncer: DDL and
    # Alembic's version bookkeeping are safer on a dedicated session.
    migration_database_url: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    brave_api_key: str = ""
    tavily_api_key: str = ""

    mcp_file_url: str = "http://localhost:8001"
    mcp_db_url: str = "http://localhost:8002"
    mcp_search_url: str = "http://localhost:8003"
    mcp_api_url: str = "http://localhost:8004"

    workspace_path: str = "/workspace"
    log_level: str = "INFO"
    environment: str = "development"
    secret_key: str = "change-me-in-production"


settings = Settings()
