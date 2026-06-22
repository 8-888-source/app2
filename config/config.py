import os
from pathlib import Path


def _load_local_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


def _database_uri():
    uri = os.getenv("DATABASE_URL", "sqlite:///notes.db").strip()

    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    elif uri.startswith("sqlite:///instance/"):
        uri = "sqlite:///" + uri[len("sqlite:///instance/"):]

    return uri


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "very_secret_key")

    SQLALCHEMY_DATABASE_URI = _database_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0").strip() == "1"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax").strip()
    
    UPLOAD_FOLDER = "static/videos"

    MAX_CONTENT_LENGTH = 500 * 1024 * 1024

    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
    STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "usd").strip().lower()
    PREMIUM_PRICE_CENTS = int(os.getenv("PREMIUM_PRICE_CENTS", "999"))
    PREMIUM_PRODUCT_NAME = os.getenv("PREMIUM_PRODUCT_NAME", "MAKSHUB Premium")
    PREMIUM_PRODUCT_DESCRIPTION = os.getenv(
        "PREMIUM_PRODUCT_DESCRIPTION",
        "Пожизненный доступ к закрытому разделу",
    )
    GOOGLE_SITE_VERIFICATION = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
