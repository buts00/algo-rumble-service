import logging
from logging.config import dictConfig
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    ENVIRONMENT: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRY: int
    JWT_REFRESH_TOKEN_EXPIRY: int

    # API SERVER
    API_SERVER_PORT: int
    API_SERVER_HOST: str

    # Main DB (Algo Rumble)
    POSTGRES_DRIVER: str
    POSTGRES_USER: str
    ALGO_RUMBLE_DB: str
    ALGO_RUMBLE_PASSWORD: str
    ALGO_RUMBLE_PORT: int
    ALGO_RUMBLE_HOST_PROD: str

    # Redis
    REDIS_HOST_PROD: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    # Kafka
    KAFKA_HOST: str
    KAFKA_PORT: int
    PLAYER_QUEUE_TOPIC: str
    MATCH_EVENTS_TOPIC: str

    # External APIs
    ONECOMPILER_API_KEY: str
    ONECOMPILER_API_HOST: str

    # DigitalOcean
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_ENDPOINT_URL: str
    AWS_BUCKET_NAME: str
    AWS_REGION: str
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        ignored_types=(int, float, bool, str),
    )

    # Computed field for ALGO_RUMBLE_DB_URL
    @property
    def ALGO_RUMBLE_DB_URL(self) -> str:
        return f"{self.POSTGRES_DRIVER}://{self.POSTGRES_USER}:{self.ALGO_RUMBLE_PASSWORD}@{self.ALGO_RUMBLE_HOST}:{self.ALGO_RUMBLE_PORT}/{self.ALGO_RUMBLE_DB}"

    @property
    def API_BASE_URL(self) -> str:
        return f"http://{self.API_SERVER_HOST}:{self.API_SERVER_PORT}"

    @property
    def REDIS_HOST(self) -> str:
        if self.ENVIRONMENT == "local":
            return "localhost"
        return self.REDIS_HOST_PROD

    @property
    def ALGO_RUMBLE_HOST(self) -> str:
        if self.ENVIRONMENT == "local":
            return "localhost"
        return self.ALGO_RUMBLE_HOST_PROD



Config = Settings()

# Ensure logs directory exists
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)


def configure_logging():
    """Configure logging for the application."""
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": Config.LOG_LEVEL,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filename": Config.LOG_FILE,
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "level": Config.LOG_LEVEL,
            },
        },
        "loggers": {
            "app": {
                "handlers": ["console", "file"],
                "level": Config.LOG_LEVEL,
                "propagate": False,
            },
            "auth": {
                "handlers": ["console", "file"],
                "level": Config.LOG_LEVEL,
                "propagate": False,
            },
            "match": {
                "handlers": ["console", "file"],
                "level": Config.LOG_LEVEL,
                "propagate": False,
            },
            "db": {
                "handlers": ["console", "file"],
                "level": Config.LOG_LEVEL,
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": Config.LOG_LEVEL,
        },
    }
    dictConfig(log_config)
    return logging.getLogger("app")


# Initialize logger
logger = configure_logging()
