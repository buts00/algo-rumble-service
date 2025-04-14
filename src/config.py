import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRY = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRY"))
    JWT_REFRESH_TOKEN_EXPIRY = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRY"))

    # API SERVER
    API_SERVER_PORT: str = int(os.getenv("API_SERVER_PORT"))
    API_SERVER_HOST: str

    # Main DB (Algo Rumble)
    POSTGRES_DRIVER: str
    POSTGRES_USER: str
    ALGO_RUMBLE_DB: str
    ALGO_RUMBLE_PASSWORD: str
    ALGO_RUMBLE_PORT = int(os.getenv("ALGO_RUMBLE_PORT"))
    ALGO_RUMBLE_HOST: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT = int(os.getenv("REDIS_PORT"))
    REDIS_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        strict=True,
        ignored_types=(int, float, bool, str),
    )

    # Computed field for ALGO_RUMBLE_DB_URL
    @property
    def ALGO_RUMBLE_DB_URL(self) -> str:
        return f"{self.POSTGRES_DRIVER}://{self.POSTGRES_USER}:{self.ALGO_RUMBLE_PASSWORD}@{self.ALGO_RUMBLE_HOST}:5432/{self.ALGO_RUMBLE_DB}"

    @property
    def API_BASE_URL(self) -> str:
        return f"http://{self.API_SERVER_HOST}:{self.API_SERVER_PORT}"


Config = Settings()
