import logging
import logging.handlers
import json
import socket
import os

LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("APP_LOG_FILE", "app.log")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "hostname": socket.gethostname(),
        }

        # Ajout des champs extra
        for key, value in record.__dict__.items():
            if key not in ("args", "msg", "levelname", "levelno", "name"):
                log[key] = value

        return json.dumps(log)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    if not logger.handlers:

        # Handler rotating file
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=5_000_000,
            backupCount=3
        )
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

        # Handler to aggregator
        syslog_handler = logging.handlers.SysLogHandler(
            address=("localhost", 514)
        )
        syslog_handler.setFormatter(JsonFormatter())
        logger.addHandler(syslog_handler)

        # Handler console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JsonFormatter())
        logger.addHandler(console_handler)

    return logger
