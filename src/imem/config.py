from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://127.0.0.1:27017/?directConnection=true"
    mongodb_db: str = "imem"
    anthropic_api_key: str = ""
    voyage_api_key: str = ""

    agent_model: str = "claude-sonnet-4-6"
    embed_model: str = "voyage-3-large"
    embed_dims: int = 1024

    max_agent_steps: int = 12
    recall_top_k: int = 3
    min_similarity: float = 0.60

    tick_seconds: int = 10
    seed_days: int = 7


settings = Settings()
