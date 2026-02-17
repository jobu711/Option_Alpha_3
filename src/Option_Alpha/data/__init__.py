"""Persistence layer for Option Alpha.

Re-exports the main public API: Database for connection management,
Repository for typed query operations.
"""

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository

__all__ = ["Database", "Repository"]
