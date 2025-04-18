from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
    ALGO_RUMBLE_HOST: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    # Kafka
    KAFKA_HOST: str
    KAFKA_PORT: int
    PLAYER_QUEUE_TOPIC: str
    MATCH_EVENTS_TOPIC: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
