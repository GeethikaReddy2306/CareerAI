from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Career Intelligence Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/career_db"

    # Security & JWT
    SECRET_KEY: str = "e83a9f0187c3405c92c908f90cba7dcfa2dbe76e319e34a6df912c96c4eb827a"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # OpenAI API
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"


    # Upload configuration
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf"]
    ALLOWED_MIME_TYPES: list[str] = ["application/pdf"]

    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resumes_upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR) / "resumes"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()

