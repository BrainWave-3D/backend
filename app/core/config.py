from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = Field(default="BrainWave3D API")
    environment: str = Field(default="development")
    mongo_uri: str = Field(..., alias="MONGO_URI")
    mongo_db_name: str = Field(default="brainwave3d", alias="MONGO_DB_NAME")
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=60 * 24 * 7, alias="REFRESH_TOKEN_EXPIRE_MINUTES")
    ml_model_path: str | None = Field(default=None, alias="ML_MODEL_PATH")
    llm_provider: str = Field(default="groq", alias="LLM_PROVIDER")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    llm_model_name: str = Field(default="llama-3.1-8b-instant", alias="LLM_MODEL_NAME")
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=512, ge=1, alias="LLM_MAX_TOKENS")
    chat_system_prompt: str = Field(
        default=(
            "You are a supportive assistant for BrainWave3D users. "
            "Use provided context carefully, be concise, and clearly state uncertainty when needed."
        ),
        alias="CHAT_SYSTEM_PROMPT",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]


settings = get_settings()
