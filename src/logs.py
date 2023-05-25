import logging

from src import constants
from logging import Logger, handlers
from pathlib import Path


root_log = logging.getLogger()

format_string = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
log_format = logging.Formatter(format_string)

if constants.FILE_LOGGING:
    log_file = Path("logs", "bot.log")
    log_file.parent.mkdir(exist_ok=True)
    file_handler = handlers.RotatingFileHandler(log_file, maxBytes=5242880, backupCount=7, encoding="utf8")
    file_handler.setFormatter(log_format)
    root_log.addHandler(file_handler)
    
root_log.setLevel(logging.DEBUG if constants.DEBUG_MODE else logging.INFO)