from functools import lru_cache
import os
import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Prefer a real .env; fall back to committed examples for first-run clones.
_DOTENV_CANDIDATES = (".env", ".env.example", "env.example")


def resolve_dotenv_path() -> Path | None:
    """Return the first existing dotenv file, or None."""
    for name in _DOTENV_CANDIDATES:
        path = Path(name)
        if path.is_file():
            return path
    return None


def _env_files_for_settings() -> tuple[str, ...]:
    """Load examples first, then `.env` last so a real `.env` wins when both exist.

    Missing files are skipped by pydantic-settings, so a clone with only
    ``.env.example`` still boots.
    """
    return (".env.example", "env.example", ".env")


_ENV_FILE = Path(".env")


@lru_cache
def get_settings():
    path = resolve_dotenv_path()
    candidates = [path] if path is not None else list(_env_files_for_settings())
    values: dict[str, str] = {}
    for candidate in candidates:
        env_path = Path(candidate)
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key in {"DATABASE_URI", "SECRET_KEY", "ENV", "APP_PORT", "CONFIG_PASSWORD"}:
            values[key] = value
    return Settings(**values)


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def set_runtime_env(mode: str) -> str:
    """Switch ENV at runtime (and persist to .env when that file exists)."""
    normalized = mode.strip().lower()
    if normalized in {"prod", "production"}:
        value = "production"
    elif normalized in {"dev", "development"}:
        value = "development"
    else:
        raise ValueError("ENV must be production or development")

    os.environ["ENV"] = value
    clear_settings_cache()
    _upsert_dotenv("ENV", value)
    return value


def _upsert_dotenv(key: str, value: str) -> None:
    # Never rewrite the committed example files — only a real `.env`.
    if not _ENV_FILE.is_file():
        return
    text = _ENV_FILE.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
    line = f'{key}="{value}"'
    if pattern.search(text):
        text = pattern.sub(line, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    _ENV_FILE.write_text(text, encoding="utf-8")


def mask_secret(value: str | None, *, keep_tail: int = 4) -> str:
    if not value:
        return "(unset)"
    if len(value) <= keep_tail:
        return "*" * len(value)
    return "*" * (len(value) - keep_tail) + value[-keep_tail:]


def mask_database_uri(uri: str) -> str:
    """Hide credentials in database URLs for the config panel."""
    if "://" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    if "@" in rest and ":" in rest.split("@", 1)[0]:
        userinfo, hostpart = rest.split("@", 1)
        user = userinfo.split(":", 1)[0]
        return f"{scheme}://{user}:****@{hostpart}"
    return uri


class Settings(BaseSettings):
    database_uri: str
    secret_key: str
    env: str
    config_password: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires: int = 30
    app_host: str = "0.0.0.0"
    app_port: int = 5000
    db_pool_size: int = 10
    db_additional_overflow: int = 10
    db_pool_timeout: int = 10
    db_pool_recycle: int = 10

    @field_validator("app_port", mode="before")
    @classmethod
    def port_from_render(cls, value: object) -> object:
        # Render sets PORT. An explicit --port on the CLI still wins in cmd_run.
        port = os.environ.get("PORT")
        if port:
            return int(port)
        return value

    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )
