"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "ielts_ai_mastery"

    # Auth
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    # AI
    ai_provider: str = "openai"  # openai | anthropic | ollama
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # OCR (scanned/image PDF fallback via pytesseract + Pillow).
    ocr_enabled: bool = True
    ocr_dpi: int = 200
    ocr_min_chars_per_page: int = 80
    ocr_language: str = "eng"
    ocr_max_pages: int = 0  # 0 / empty => process all pages

    @field_validator("ocr_max_pages", mode="before")
    @classmethod
    def _empty_max_pages_is_zero(cls, v):
        # OCR_MAX_PAGES= (empty string) should mean "all pages".
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0
        return v

    @field_validator("ocr_enabled", mode="before")
    @classmethod
    def _coerce_ocr_enabled(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        return v

    # Temp dir for transient parsing only (never permanent storage).
    upload_dir: str = "./storage/tmp"

    # Amazon S3 (primary store for original/binary files).
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-central-1"
    aws_s3_bucket: str = ""
    aws_s3_public_base_url: str = ""  # e.g. CloudFront URL; optional
    s3_presign_expiry: int = 3600  # seconds

    # URL prefix when the reverse proxy forwards /api/* without stripping (Dokploy).
    # Local dev: leave empty. Production: API_ROOT_PREFIX=/api
    api_root_prefix: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def api_prefix(self) -> str:
        p = self.api_root_prefix.strip().rstrip("/")
        if not p:
            return ""
        return p if p.startswith("/") else f"/{p}"

    @property
    def cors_origins_list(self) -> list[str]:
        # Browsers send Origin without a trailing slash; normalize env values.
        origins: list[str] = []
        for o in self.cors_origins.split(","):
            o = o.strip().rstrip("/")
            if o:
                origins.append(o)
        return origins

    @property
    def s3_enabled(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key and self.aws_s3_bucket)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
