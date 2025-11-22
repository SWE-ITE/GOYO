"""
GOYO ANC Server Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """ANC 서버 환경 설정"""

    # Server
    ANC_SERVER_HOST: str = "0.0.0.0"
    ANC_SERVER_PORT: int = 8001

    # MQTT
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    
    # Audio Processing
    SAMPLE_RATE: int = 16000  # Hz (AI 요구사항)
    CHUNK_SIZE: int = 16000  # samples (1초 @ 16kHz)
    CHANNELS: int = 1  # mono
    AUDIO_FORMAT: str = "int16"  # 16-bit PCM
    
    # Buffer Settings
    BUFFER_DURATION: float = 0.1  # 100ms
    MAX_BUFFER_SIZE: int = 10  # 최대 버퍼 청크 수
    
    # ANC Settings
    LATENCY_TARGET_MS: int = 30  # 목표 지연시간
    
    # Model Paths (Phase 5에서 사용)
    NOISE_CLASSIFIER_MODEL: str = "models/noise_classifier.pth"
    TRANSFER_FUNCTION_MODEL: str = "models/transfer_function.pth"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()