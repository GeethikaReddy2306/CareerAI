from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Career Intelligence Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # ── MongoDB ────────────────────────────────────────────────────────────────
    # Set MONGODB_URL to your Atlas connection string in .env (never commit it).
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "careerai"

    # ── Security & JWT ────────────────────────────────────────────────────────
    # CHANGE THIS in production — use a long random string (32+ chars).
    SECRET_KEY: str = "e83a9f0187c3405c92c908f90cba7dcfa2dbe76e319e34a6df912c96c4eb827a"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── OpenAI API ────────────────────────────────────────────────────────────
    # Optional — deterministic ATS scoring works without it.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed frontend origins.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"

    # ── File uploads ──────────────────────────────────────────────────────────
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
    def allowed_origins_list(self) -> list[str]:
        """Parse the comma-separated ALLOWED_ORIGINS string into a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def resumes_upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR) / "resumes"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
