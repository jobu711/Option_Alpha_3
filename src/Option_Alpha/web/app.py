"""FastAPI app factory, Jinja2 config, static files, and custom template filters."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from Option_Alpha.data.database import Database
from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).parent
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

templates: Jinja2Templates


# ---------------------------------------------------------------------------
# Custom Jinja2 Filters
# ---------------------------------------------------------------------------


def money_filter(value: str | Decimal | None) -> str:
    """Format Decimal/string as currency: '185.00' -> '$185.00'."""
    if value is None:
        return "\u2014"
    try:
        d = Decimal(str(value))
        return f"${d:,.2f}"
    except (InvalidOperation, ValueError):
        return str(value)


def pct_filter(value: float | None) -> str:
    """Format 0-1 float as percentage: 0.723 -> '72.3%'."""
    if value is None:
        return "\u2014"
    return f"{value * 100:.1f}%"


def pct_raw_filter(value: float | None) -> str:
    """Format already-percentage float: 72.3 -> '72.3%'."""
    if value is None:
        return "\u2014"
    return f"{value:.1f}%"


def timeago_filter(value: datetime | None) -> str:
    """Relative time: datetime -> '3 hours ago'."""
    if value is None:
        return "\u2014"
    now = datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    diff = now - value
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins} min{'s' if mins != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    return f"{months} month{'s' if months != 1 else ''} ago"


def signal_color_filter(direction: str | None) -> str:
    """SignalDirection -> Tailwind color class."""
    colors = {
        "BULLISH": "text-emerald-400",
        "BEARISH": "text-red-400",
        "NEUTRAL": "text-zinc-400",
    }
    return colors.get(direction.upper() if direction else "", "text-zinc-400")


# ---------------------------------------------------------------------------
# Database Dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[Database]:
    """Async dependency that yields a connected Database and ensures cleanup."""
    db = Database("data/option_alpha.db")
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global templates  # noqa: PLW0603

    app = FastAPI(title="Option Alpha", docs_url=None, redoc_url=None)

    # Jinja2 templates
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    templates.env.filters["money"] = money_filter
    templates.env.filters["pct"] = pct_filter
    templates.env.filters["pct_raw"] = pct_raw_filter
    templates.env.filters["timeago"] = timeago_filter
    templates.env.filters["signal_color"] = signal_color_filter

    # Jinja2 globals
    templates.env.globals["disclaimer_text"] = DISCLAIMER_TEXT

    # Routes
    from Option_Alpha.web.routes import (
        dashboard,
        debate,
        health,
        scanner,
        settings,
        universe,
        watchlists,
    )

    app.include_router(dashboard.router)
    app.include_router(scanner.router)
    app.include_router(debate.router)
    app.include_router(watchlists.router)
    app.include_router(universe.router)
    app.include_router(health.router)
    app.include_router(settings.router)

    # Static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Health check
    @app.get("/api/health")
    async def health_check() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    logger.info("Option Alpha web app created")
    return app
