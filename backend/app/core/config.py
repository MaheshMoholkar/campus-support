from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Configuration from environment variables; `.env.lab` is written by `lab up`."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env.lab", REPO_ROOT / "backend" / ".env"),
        extra="ignore",
    )

    database_url: str
    session_secret: str = Field(
        min_length=32
    )  # no default: a known secret lets anyone forge a session
    session_hours: int = 12
    cookie_secure: bool = False
    s3_endpoint: str = ""
    s3_region: str = "garage"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_attachments: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        # SQLAlchemy needs the driver in the scheme; `.env.lab` gives the plain form.
        for prefix in ("postgresql://", "postgres://"):
            if self.database_url.startswith(prefix):
                return "postgresql+psycopg://" + self.database_url[len(prefix) :]
        return self.database_url


settings = Settings()  # pyright: ignore[reportCallIssue]
