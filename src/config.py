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
    API_BASE_URL: str

    # Main DB (Algo Rumble)
    POSTGRES_DRIVER: str
    POSTGRES_USER: str
    ALGO_RUMBLE_DB: str
    ALGO_RUMBLE_PASSWORD: str
    ALGO_RUMBLE_PORT = int(os.getenv("ALGO_RUMBLE_PORT"))
    ALGO_RUMBLE_HOST: str

    # Judge0 DB
    JUDGE0_DB: str
    JUDGE0_DB_PASSWORD: str
    JUDGE0_DB_PORT = int(os.getenv("JUDGE0_DB_PORT"))
    JUDGE0_DB_HOST: str

    # Judge0 server
    JUDGE0_AUTH_TOKEN: str
    JUDGE0_URL: str
    JUDGE0_SERVER_PORT = int(os.getenv("JUDGE0_SERVER_PORT"))

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
        return f"{self.POSTGRES_DRIVER}://{self.POSTGRES_USER}:{self.ALGO_RUMBLE_PASSWORD}@{self.ALGO_RUMBLE_HOST}:{self.ALGO_RUMBLE_PORT}/{self.ALGO_RUMBLE_DB}"

    # Computed field for JUDGE0_DB_URL
    @property
    def JUDGE0_DB_URL(self) -> str:
        return f"{self.POSTGRES_DRIVER}://{self.POSTGRES_USER}:{self.JUDGE0_DB_PASSWORD}@{self.JUDGE0_DB_HOST}:{self.JUDGE0_DB_PORT}/{self.JUDGE0_DB}"


Config = Settings()
