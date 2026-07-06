"""
Logging configuration with rotation for production.

Uses Python's logging.handlers.RotatingFileHandler to automatically
rotate log files when they reach a certain size, keeping the last N
backups. This prevents the log directory from filling up the disk
on the free-tier Cloud Run instance (which has limited storage).
"""
import logging
import logging.handlers
import os
from pathlib import Path

from app.core.config import settings


# Default values for free-tier deploys.
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "app.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file
DEFAULT_BACKUP_COUNT = 3                # keep app.log, app.log.1, app.log.2, app.log.3


def setup_logging(
    log_dir: str = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> None:
    """
    Configure root logger with console + rotating file handlers.

    - Console: always enabled
    - File: enabled unless DEBUG=True (avoid noise during local dev)
    - Rotation: max 5MB per file, keep 3 backups (~20MB total)
    """
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Reset existing handlers (avoid duplicates on reload)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ==== Console handler (stdout) ====
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ==== Rotating file handler ====
    if not settings.DEBUG:
        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_path / log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, PermissionError) as exc:
            # If we cannot write to the log directory (e.g. read-only FS),
            # fall back to console-only logging instead of crashing the app.
            console_handler.warning(
                "Could not create rotating log file (%s). Using console only.",
                exc,
            )

    # Tame noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)