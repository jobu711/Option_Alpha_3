"""FastAPI web layer for Option Alpha.

Re-exports the application factory so consumers can import directly:
    from Option_Alpha.web import create_app
"""

from Option_Alpha.web.app import create_app

__all__ = ["create_app"]
