"""앱 전역 설정. .env 값을 읽어 옵니다."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 앱 공통
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # RDB (미설정 시 SQLite, 운영 시 postgresql+asyncpg://...)
    DATABASE_URL: str = "sqlite+aiosqlite:///./rainbow_bridge.db"

    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "rainbow_bridge"

    # PERSO API (평가/시연)
    PERSO_API_KEY: str = ""
    PERSO_API_BASE_URL: str = ""

    # 로컬 LLM (개발) — AI 담당이 .env에 채움
    LLM_PROVIDER: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""

    # TTS
    TTS_PROVIDER: str = ""
    TTS_API_KEY: str = ""

    # LivePortrait
    LIVEPORTRAIT_MODE: str = "local"  # "local" | "remote"
    LIVEPORTRAIT_API_URL: str = ""  # remote 모드 시 GPU 서버 URL
    REPLICATE_API_TOKEN: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # 안전 라우팅 (변경 금지)
    CRISIS_HOTLINE: str = "1393"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
