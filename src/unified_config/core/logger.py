import logging

# Custom log format including only PID
LOG_FORMAT = "[%(asctime)s] PID: %(process)d | %(levelname)s: %(message)s"

# Apply logging configuration
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# Create logger instance
logger = logging.getLogger("unified_config")
