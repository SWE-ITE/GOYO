from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # MQTT
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = "goyo_backend"
    MQTT_PASSWORD: str = ""
    MQTT_BROKER: Optional[str] = None  # Deprecated, use MQTT_BROKER_HOST
    MQTT_PORT: Optional[int] = None  # Deprecated, use MQTT_BROKER_PORT

    # AI Server
    AI_SERVER_HOST: str = "localhost"
    AI_SERVER_PORT: int = 8001

    # Security
    SECRET_KEY: str
    JWT_SECRET_KEY: Optional[str] = None  # Alias for SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Audio
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    CHUNK_SIZE: int = 16000

    class Config:
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Backward compatibility
        if self.MQTT_BROKER and not self.MQTT_BROKER_HOST:
            self.MQTT_BROKER_HOST = self.MQTT_BROKER
        if self.MQTT_PORT and not self.MQTT_BROKER_PORT:
            self.MQTT_BROKER_PORT = self.MQTT_PORT
        if self.JWT_SECRET_KEY and not self.SECRET_KEY:
            self.SECRET_KEY = self.JWT_SECRET_KEY

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()