"""FastAPI route modules for Option Alpha.

Re-exports all routers so the application factory can import them:
    from Option_Alpha.web.routes import health_router, scan_router, debate_router
"""

from Option_Alpha.web.routes.debate import router as debate_router
from Option_Alpha.web.routes.health import router as health_router
from Option_Alpha.web.routes.report import router as report_router
from Option_Alpha.web.routes.scan import router as scan_router
from Option_Alpha.web.routes.settings import router as settings_router
from Option_Alpha.web.routes.ticker import router as ticker_router
from Option_Alpha.web.routes.universe import router as universe_router
from Option_Alpha.web.routes.watchlist import router as watchlist_router

__all__ = [
    "debate_router",
    "health_router",
    "report_router",
    "scan_router",
    "settings_router",
    "ticker_router",
    "universe_router",
    "watchlist_router",
]
