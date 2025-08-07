import logging

logger = logging.getLogger("botmark")
logging.basicConfig(level=logging.INFO)

def log_info(message: str):
    logger.info(message)

def log_error(message: str):
    logger.error(message)