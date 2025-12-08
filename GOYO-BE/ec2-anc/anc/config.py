"""
GOYO ANC Server Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """ANC 서버 환경 설정"""

    
    ANC_SERVER_HOST: str = "0.0.0.0"
    ANC_SERVER_PORT: int = 8001

    
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    
    
    SAMPLE_RATE: int = 16000  
    CHUNK_SIZE: int = 16000  
    CHANNELS: int = 1  
    AUDIO_FORMAT: str = "int16"  
    
    
    BUFFER_DURATION: float = 0.1  
    MAX_BUFFER_SIZE: int = 10  
    
    
    LATENCY_TARGET_MS: int = 30  
    
    
    NOISE_CLASSIFIER_MODEL: str = "models/noise_classifier.pth"
    TRANSFER_FUNCTION_MODEL: str = "models/transfer_function.pth"
    
    
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()