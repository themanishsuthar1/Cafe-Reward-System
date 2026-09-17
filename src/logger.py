import logging
import sys
import os
from typing import Optional

DEFAULT_LOG_FILE = "cafe_rewards.log"

def setup_logger(
    name: str = "cafe_rewards",
    log_file: Optional[str] = DEFAULT_LOG_FILE,
    level: int = logging.INFO
) -> logging.Logger:
    """
    Configures and returns a centralized logger with structured formatting,
    console streaming, and optional file output.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger is already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Log format: [TIMESTAMP] [LEVEL] [MODULE:LINE] - MESSAGE
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Stream Handler (stdout console)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (append to cafe_rewards.log)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def get_logger(module_name: str) -> logging.Logger:
    """
    Returns a child logger scoped to a specific module name.
    Example usage: logger = get_logger(__name__)
    """
    base_logger = setup_logger()
    return base_logger.getChild(module_name)

# Root application logger instance
logger = setup_logger()
