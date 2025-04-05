# src/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# The .env file is in the parent directory of "src"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

# Load the .env so environment variables are set before Pydantic reads them
load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    # JWT configuration
    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRY: int = 3600
    JWT_REFRESH_TOKEN_EXPIRY: int = 2592000

    # API & Database configuration
    API_BASE_URL: str
    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Judge0 Database configuration
    JUDGE0_DB_URL: str
    JUDGE0_DB: str
    JUDGE0_PASSWORD: str
    JUDGE0_USER: str
    JUDGE0_AUTH_TOKEN: str
    JUDGE0_URL: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str

    # Pydantic Settings Config
    model_config = SettingsConfigDict(
        # Instructs Pydantic to look for .env in the parent directory of "src"
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )


Config = Settings()
