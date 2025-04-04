from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    JWT_ACCESS_TOKEN_EXPIRY: int = 3600
    JWT_REFRESH_TOKEN_EXPIRY: int = 2592000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


Config = Settings()
