from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    JWT_ACCESS_TOKEN_EXPIRY: int = 3600
    JWT_REFRESH_TOKEN_EXPIRY: int = 2592000
    JUDGE0_AUTH_TOKEN: str
    JUDGE0_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


Config = Settings()
