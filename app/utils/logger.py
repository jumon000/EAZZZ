import logging
import sys
import os

def setup_logging(
    log_level_str: str = "INFO",
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    ):
    """
    Configures basic logging for the application.
    Call this once at application startup.
    """
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    if not logging.root.handlers:
        logging.basicConfig(
            level=log_level,
            format=log_format,
            datefmt=log_date_format,
            handlers=[
                logging.StreamHandler(sys.stdout) 
       
            ]
        )
        logger = logging.getLogger(__name__)
        logger.info(f"Root logging configured with level: {logging.getLevelName(log_level)}")
    else:
        
        logging.getLogger().setLevel(log_level)
        logger = logging.getLogger(__name__)
        logger.info(f"Logging was already configured. Root logger level set to: {logging.getLevelName(log_level)}")


