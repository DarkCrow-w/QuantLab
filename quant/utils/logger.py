import sys

from loguru import logger

# Remove default handler and add a clean one
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)


def setup_file_logger(path: str, level: str = "DEBUG") -> None:
    logger.add(path, level=level, rotation="10 MB", retention="7 days")
