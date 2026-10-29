from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Career Intelligence Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "careerai"

    # Security and JWT
    # Set SECRET_KEY through environment variables in production.
    SECRET_KEY: str = "replace-this-with-a-secure-random-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = 45.0
    OPENAI_MAX_RETRIES: int = 0
    # Profile-based interview questions are an explicit offline mode. They are
    # never used to hide rejected credentials or an invalid provider response.
    INTERVIEW_PROFILE_FALLBACK_ENABLED: bool = False
    # Explicit presentation/demo mode. When enabled, interview flows do not
    # call OpenAI and instead return clearly labelled deterministic results.
    # This is useful for an offline demonstration, not a substitute for a
    # valid server-side API credential in normal operation.
    INTERVIEW_DEMO_MODE: bool = False

    # CORS: comma-separated allowed frontend origins
    ALLOWED_ORIGINS: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:4173,"
        "http://127.0.0.1:4173,"
        "https://career-ai-beige.vercel.app"
    )

    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS: list[str] = [".pdf"]
    ALLOWED_MIME_TYPES: list[str] = ["application/pdf"]

    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        # Resolve relative to the backend package rather than the process CWD.
        # This keeps `uvicorn app.main:app` and root-level launch commands from
        # silently loading different environment files.
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated allowed frontend origins."""
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def resumes_upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR) / "resumes"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
