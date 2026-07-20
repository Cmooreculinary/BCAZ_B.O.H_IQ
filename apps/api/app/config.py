from __future__ import annotations

import os
import secrets
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        self.app_name = "BCAz B.O.H Global IQ"
        self.environment = os.getenv("APP_ENV", "development").strip().lower()
        self.api_prefix = "/api/v1"
        self.app_storage = os.getenv("APP_STORAGE", "file").strip().lower()
        self.data_file = Path(os.getenv("DATA_FILE", "./data/bcaz-boh-iq.json"))
        self.mongodb_uri = os.getenv("MONGODB_URI", "").strip()
        self.mongodb_database = os.getenv("MONGODB_DATABASE", "bcaz_boh_iq").strip()
        configured_auth_secret = os.getenv("AUTH_SECRET", "").strip()
        self.auth_secret_configured = bool(configured_auth_secret)
        self.auth_secret = configured_auth_secret or secrets.token_urlsafe(48)
        self.access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "480"))
        self.seed_demo_data = _as_bool(
            os.getenv("SEED_DEMO_DATA"), default=self.environment != "production"
        )
        self.bootstrap_admin_email = os.getenv(
            "BOOTSTRAP_ADMIN_EMAIL", "owner@bcaz.example"
        ).strip().lower()
        self.bootstrap_admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        self.demo_password = os.getenv("DEMO_PASSWORD", "")
        raw_origins = os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
        self.cors_origins = [
            origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()
        ]

    def validate_runtime(self) -> None:
        if self.app_storage not in {"memory", "file", "mongo"}:
            raise RuntimeError("APP_STORAGE must be memory, file, or mongo.")
        if "*" in self.cors_origins:
            raise RuntimeError("Wildcard CORS origins are prohibited.")
        if self.app_storage == "mongo" and not self.mongodb_uri:
            raise RuntimeError("MONGODB_URI is required when APP_STORAGE=mongo.")
        if self.seed_demo_data and self.environment != "production" and len(self.demo_password) < 12:
            raise RuntimeError("DEMO_PASSWORD must contain at least 12 characters when demo data is enabled.")
        if self.environment == "production":
            if not self.auth_secret_configured or len(self.auth_secret) < 32:
                raise RuntimeError("Production AUTH_SECRET must contain at least 32 characters.")
            if not self.bootstrap_admin_password:
                raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD is required in production.")
            if len(self.bootstrap_admin_password) < 12:
                raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters.")


settings = Settings()
