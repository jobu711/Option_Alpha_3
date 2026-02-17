"""Health checks for all external service dependencies.

Checks Ollama (local LLM), yfinance (market data), and SQLite (persistence)
availability. Each check runs independently with its own timeout so a single
service being down does not block the entire health report.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Final

import httpx

from Option_Alpha.data.database import Database
from Option_Alpha.models.health import HealthStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL: Final[str] = "http://localhost:11434"
OLLAMA_TAGS_ENDPOINT: Final[str] = f"{OLLAMA_BASE_URL}/api/tags"
REQUIRED_OLLAMA_MODEL: Final[str] = "llama3.1:8b"

# Canary ticker for yfinance health check
YFINANCE_CANARY_TICKER: Final[str] = "SPY"
YFINANCE_CANARY_PERIOD: Final[str] = "1d"

# Timeouts for individual health checks (seconds)
OLLAMA_CHECK_TIMEOUT: Final[float] = 5.0
YFINANCE_CHECK_TIMEOUT: Final[float] = 10.0
SQLITE_CHECK_TIMEOUT: Final[float] = 5.0


class HealthService:
    """Check availability of all external dependencies.

    Runs independent checks against Ollama, yfinance, and SQLite,
    returning a typed HealthStatus model with per-service results.

    Usage::

        health = HealthService(database=db)
        status = await health.check_all()
        if not status.ollama_available:
            logger.warning("Ollama is down, will use data-driven fallback.")
    """

    def __init__(self, database: Database | None = None) -> None:
        self._database = database

        logger.info("HealthService initialized.")

    async def check_all(self) -> HealthStatus:
        """Run all health checks and return a consolidated status.

        Each check is independent: one service being down does not affect
        the others. All checks run concurrently via asyncio.gather.

        Returns:
            HealthStatus with per-service availability flags.
        """
        ollama_result: tuple[bool, list[str]]
        yfinance_result: bool
        sqlite_result: bool

        results = await asyncio.gather(
            self._check_ollama_with_models(),
            self.check_yfinance(),
            self.check_database(),
            return_exceptions=True,
        )

        # Process Ollama result
        if isinstance(results[0], BaseException):
            logger.warning("Ollama health check raised: %s", results[0])
            ollama_result = (False, [])
        else:
            ollama_result = results[0]

        # Process yfinance result
        if isinstance(results[1], BaseException):
            logger.warning("yfinance health check raised: %s", results[1])
            yfinance_result = False
        else:
            yfinance_result = results[1]

        # Process SQLite result
        if isinstance(results[2], BaseException):
            logger.warning("SQLite health check raised: %s", results[2])
            sqlite_result = False
        else:
            sqlite_result = results[2]

        status = HealthStatus(
            ollama_available=ollama_result[0],
            yfinance_available=yfinance_result,
            sqlite_available=sqlite_result,
            ollama_models=ollama_result[1],
            last_check=datetime.datetime.now(datetime.UTC),
        )

        logger.info(
            "Health check complete: ollama=%s yfinance=%s sqlite=%s models=%s",
            status.ollama_available,
            status.yfinance_available,
            status.sqlite_available,
            status.ollama_models,
        )

        return status

    async def check_ollama(self) -> bool:
        """Check if Ollama is running and has the required model.

        Returns:
            True if Ollama responds and has the llama3.1:8b model.
        """
        result = await self._check_ollama_with_models()
        return result[0]

    async def check_yfinance(self) -> bool:
        """Check if yfinance can fetch data by querying the SPY canary ticker.

        Uses asyncio.to_thread since yfinance is synchronous.

        Returns:
            True if the canary fetch succeeds with non-empty data.
        """
        try:
            is_available: bool = await asyncio.wait_for(
                asyncio.to_thread(self._yfinance_canary),
                timeout=YFINANCE_CHECK_TIMEOUT,
            )
            if is_available:
                logger.debug("yfinance canary check passed.")
            else:
                logger.warning("yfinance canary check returned empty data.")
            return is_available
        except TimeoutError:
            logger.warning("yfinance canary check timed out.")
            return False
        except Exception:
            logger.warning("yfinance canary check failed.", exc_info=True)
            return False

    async def check_database(self) -> bool:
        """Check if the SQLite database is accessible.

        Verifies the database connection is live and the schema_version
        table exists (indicating migrations have been applied).

        Returns:
            True if the database is accessible and migrations are current.
        """
        if self._database is None:
            logger.debug("No database configured for health check.")
            return False

        try:
            is_available: bool = await asyncio.wait_for(
                self._sqlite_check(),
                timeout=SQLITE_CHECK_TIMEOUT,
            )
            return is_available
        except TimeoutError:
            logger.warning("SQLite health check timed out.")
            return False
        except Exception:
            logger.warning("SQLite health check failed.", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_ollama_with_models(self) -> tuple[bool, list[str]]:
        """Check Ollama availability and return (is_available, model_list).

        Returns:
            Tuple of (True if llama3.1:8b is available, list of model names).
        """
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=5.0,
                    write=5.0,
                    pool=5.0,
                ),
            ) as client:
                response = await asyncio.wait_for(
                    client.get(OLLAMA_TAGS_ENDPOINT),
                    timeout=OLLAMA_CHECK_TIMEOUT,
                )

            if response.status_code != 200:  # noqa: PLR2004
                logger.warning(
                    "Ollama returned HTTP %d.",
                    response.status_code,
                )
                return (False, [])

            data = response.json()
            models_data = data.get("models", [])
            model_names: list[str] = [
                m.get("name", "") for m in models_data if isinstance(m, dict)
            ]

            has_required = any(REQUIRED_OLLAMA_MODEL in name for name in model_names)

            if has_required:
                logger.debug(
                    "Ollama check passed: %s found in %d models.",
                    REQUIRED_OLLAMA_MODEL,
                    len(model_names),
                )
            else:
                logger.warning(
                    "Ollama running but %s not found. Available: %s",
                    REQUIRED_OLLAMA_MODEL,
                    ", ".join(model_names) if model_names else "(none)",
                )

            return (has_required, model_names)

        except TimeoutError:
            logger.warning("Ollama health check timed out.")
            return (False, [])
        except httpx.HTTPError as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return (False, [])

    @staticmethod
    def _yfinance_canary() -> bool:
        """Synchronous yfinance canary check (run via asyncio.to_thread).

        Fetches a minimal history for SPY to verify yfinance is functional.

        Returns:
            True if data was returned with at least one row.
        """
        import yfinance  # type: ignore[import-untyped]  # noqa: PLC0415

        ticker = yfinance.Ticker(YFINANCE_CANARY_TICKER)
        history_df = ticker.history(period=YFINANCE_CANARY_PERIOD)
        return len(history_df) > 0

    async def _sqlite_check(self) -> bool:
        """Verify SQLite database accessibility and migration status.

        Returns:
            True if the database responds and schema_version table exists.
        """
        if self._database is None:
            return False

        conn = self._database.connection
        # Check that we can query the schema_version table
        cursor = await conn.execute("SELECT COUNT(*) FROM schema_version")
        row = await cursor.fetchone()
        if row is None:
            logger.warning("schema_version query returned no rows.")
            return False

        migration_count: int = row[0]
        logger.debug(
            "SQLite check passed: %d migrations applied.",
            migration_count,
        )
        return True
