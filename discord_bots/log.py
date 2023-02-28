import logging
from logging import handlers

from discord_bots.config import DEBUG, LOG_FILE

level = logging.INFO if not DEBUG else logging.DEBUG


def define_default_logger():
    if LOG_FILE:
        hdlrs = [
            handlers.RotatingFileHandler(LOG_FILE, maxBytes=(10 * 1024 * 1024), backupCount=5),
            logging.StreamHandler()
        ]
    else:
        hdlrs = [logging.StreamHandler()]
    logging.basicConfig(format="%(asctime)s [%(levelname)s:%(name)s] %(message)s",
                        level=logging.WARNING,
                        handlers=hdlrs)


def define_logger(name="app"):
    log = logging.getLogger(name)
    log.propagate = False
    log.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s:%(filename)12s:%(lineno)s] %(message)s")
    console_logger = logging.StreamHandler()
    console_logger.setLevel(level)
    console_logger.setFormatter(formatter)
    log.addHandler(console_logger)
    if LOG_FILE:
        file_logger = handlers.RotatingFileHandler(LOG_FILE, maxBytes=(10 * 1024 * 1024), backupCount=5)
        file_logger.setLevel(level)
        file_logger.setFormatter(formatter)
        log.addHandler(file_logger)
    return log
