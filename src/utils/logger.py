import logging
from pathlib import Path


def build_logger() -> logging.Logger:
    logger = logging.getLogger("DynamicIsland")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logger


logger = build_logger()
