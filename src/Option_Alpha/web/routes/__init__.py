"""FastAPI route modules for Option Alpha.

Re-exports all routers so the application factory can import them:
    from Option_Alpha.web.routes import health_router
"""

from Option_Alpha.web.routes.health import router as health_router

__all__ = ["health_router"]
