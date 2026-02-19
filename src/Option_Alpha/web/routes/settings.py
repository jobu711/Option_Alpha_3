"""Settings routes — web configuration with JSON file persistence."""

import json
import logging
from pathlib import Path
from typing import Final

from fastapi import APIRouter, Form, Request
from starlette.responses import HTMLResponse

from Option_Alpha.web.app import templates

logger = logging.getLogger(__name__)

router = APIRouter()

SETTINGS_PATH: Final[Path] = Path("data/web_settings.json")

# Settings is an internal web-layer concern — a simple dict is acceptable here per
# the epic spec. This is the documented exception to the no-raw-dicts rule.
DEFAULT_SETTINGS: Final[dict[str, str | int]] = {
    "ollama_endpoint": "http://localhost:11434",
    "ollama_model": "llama3.1:8b",
    "scan_top_n": 10,
    "scan_min_volume": 100000,
    "scan_dte_min": 20,
    "scan_dte_max": 60,
}


def _load_settings() -> dict[str, str | int]:
    """Load settings from JSON file, falling back to defaults."""
    if SETTINGS_PATH.exists():
        try:
            data: dict[str, str | int] = json.loads(  # dict-ok: flat JSON config
                SETTINGS_PATH.read_text(encoding="utf-8")
            )
            return data
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read settings file, using defaults")
    return dict(DEFAULT_SETTINGS)


def _save_settings(settings: dict[str, str | int]) -> None:  # dict-ok: flat JSON config
    """Persist settings to JSON file, creating parent directories if needed."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    logger.info("Settings saved to %s", SETTINGS_PATH)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """Render the settings page with current configuration values."""
    settings = _load_settings()
    return templates.TemplateResponse(
        "pages/settings.html",
        {"request": request, "active_page": "settings", "settings": settings, "saved": False},
    )


@router.post("/settings", response_class=HTMLResponse)
async def save_settings(
    request: Request,
    ollama_endpoint: str = Form(...),  # noqa: B008
    ollama_model: str = Form(...),  # noqa: B008
    scan_top_n: int = Form(...),  # noqa: B008
    scan_min_volume: int = Form(...),  # noqa: B008
    scan_dte_min: int = Form(...),  # noqa: B008
    scan_dte_max: int = Form(...),  # noqa: B008
) -> HTMLResponse:
    """Save settings from the form and re-render the page with confirmation."""
    settings: dict[str, str | int] = {
        "ollama_endpoint": ollama_endpoint,
        "ollama_model": ollama_model,
        "scan_top_n": scan_top_n,
        "scan_min_volume": scan_min_volume,
        "scan_dte_min": scan_dte_min,
        "scan_dte_max": scan_dte_max,
    }
    _save_settings(settings)
    return templates.TemplateResponse(
        "pages/settings.html",
        {"request": request, "active_page": "settings", "settings": settings, "saved": True},
    )
