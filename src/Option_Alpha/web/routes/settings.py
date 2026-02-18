"""Application settings endpoints.

Provides read and update access to user-configurable application settings.
Settings are persisted as a JSON file in the ``data/`` directory.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Settings file path (relative to project root)
_SETTINGS_FILE = Path("data") / "web_settings.json"


# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------


class WebSettings(BaseModel):
    """User-configurable application settings.

    Persisted as a JSON file. All fields have sensible defaults so the
    application works out-of-the-box without explicit configuration.
    """

    model_config = ConfigDict(frozen=True)

    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    scan_top_n: int = 10
    scan_min_volume: int = 100
    default_dte_min: int = 20
    default_dte_max: int = 60


# ---------------------------------------------------------------------------
# Internal persistence helpers
# ---------------------------------------------------------------------------


def _load_settings() -> WebSettings:
    """Load settings from disk, returning defaults if the file is missing."""
    if _SETTINGS_FILE.exists():
        raw = _SETTINGS_FILE.read_text(encoding="utf-8")
        return WebSettings.model_validate_json(raw)
    return WebSettings()


def _save_settings(settings: WebSettings) -> None:
    """Persist settings to disk as JSON."""
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(
        json.dumps(settings.model_dump(), indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=WebSettings)
async def get_settings() -> WebSettings:
    """Return the current application settings."""
    settings = _load_settings()
    logger.info("Settings retrieved.")
    return settings


@router.put("", response_model=WebSettings)
async def update_settings(body: WebSettings) -> WebSettings:
    """Update and persist application settings.

    Accepts a full ``WebSettings`` body and replaces the stored settings
    entirely. Returns the persisted settings for confirmation.
    """
    _save_settings(body)
    logger.info("Settings updated: %s", body.model_dump())
    return body
