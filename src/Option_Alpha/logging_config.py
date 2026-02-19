"""Centralized logging configuration for CLI and web entry points."""

from __future__ import annotations

import logging
import os

LOG_FORMAT: str = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_MODULE_LOGGERS: dict[str, str] = {
    "AGENTS": "Option_Alpha.agents",
    "SERVICES": "Option_Alpha.services",
    "WEB": "Option_Alpha.web",
    "DATA": "Option_Alpha.data",
    "ANALYSIS": "Option_Alpha.analysis",
    "INDICATORS": "Option_Alpha.indicators",
    "REPORTING": "Option_Alpha.reporting",
}


def configure_logging(
    *,
    level: str = "",
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    """Configure root logger with consistent format across CLI and web.

    Priority: verbose > quiet > level param > LOG_LEVEL env > INFO default.
    Uses force=True to override uvicorn's prior root logger config.
    Reads LOG_LEVEL_{MODULE} env vars for per-module overrides.
    """
    if verbose:
        effective = logging.DEBUG
    elif quiet:
        effective = logging.WARNING
    elif level:
        effective = getattr(logging, level.upper(), logging.INFO)
    else:
        env_level = os.environ.get("LOG_LEVEL", "INFO")
        effective = getattr(logging, env_level.upper(), logging.INFO)

    logging.basicConfig(level=effective, format=LOG_FORMAT, force=True)

    # Demote uvicorn access logger (our middleware replaces it)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Apply per-module overrides from env vars
    for key, logger_name in _MODULE_LOGGERS.items():
        env_key = f"LOG_LEVEL_{key}"
        module_level = os.environ.get(env_key)
        if module_level:
            resolved = getattr(logging, module_level.upper(), None)
            if resolved is not None:
                logging.getLogger(logger_name).setLevel(resolved)
