import logging
import colorlog
from datetime import datetime
import os
import sys

LOG_DIR = "logs"
LOG_FILE = f"{LOG_DIR}/nexus_syncer-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log"

# Logger
def setup_logger(name, debug=False, logToFile=True):
  logger = logging.getLogger(name)
  logger.setLevel(logging.INFO)
  if debug:
    logger.setLevel(logging.DEBUG)
  console_handler = logging.StreamHandler(sys.stdout)
  console_formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
    log_colors={"DEBUG": "cyan", "INFO": "green", "WARNING": "yellow", "ERROR": "red", "CRITICAL": "bold_red"},
  )
  console_handler.setFormatter(console_formatter)
  logger.addHandler(console_handler)
  # Log to file
  if logToFile:
    os.makedirs(LOG_DIR, exist_ok=True)
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="w")
    file_formatter = logging.Formatter(log_format)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
  logger.propagate = False
  return logger

# log = setup_logger(__name__)
