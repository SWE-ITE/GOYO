"""
ANC Controller
Generates anti-noise signal (Phase 5에서 고도화 예정)
"""
import numpy as np
import logging
from typing import Dict, Optional
import time

from config import settings
from mqtt_publisher import mqtt_publisher

logger = logging.getLogger(__name__)


class ANCController:
    """Active Noise Control 신호 생성"""
    
    def __init__(self):
        
        self.active_users: Dict[str, bool] = {}

    def start(self, user_id: str):
        """ANC 시작"""
        self.active_users[user_id] = True
        logger.info(f"▶️  ANC started for user {user_id}")

    def stop(self, user_id: str):
        """ANC 중지"""
        self.active_users[user_id] = False
        logger.info(f"⏹️  ANC stopped for user {user_id}")
    
    def is_active(self, user_id: str) -> bool:
        """ANC 활성 상태 확인"""
        return self.active_users.get(user_id, False)
    
    def generate_anti_noise(
        self,
        reference_data: np.ndarray,
        error_data: np.ndarray,
        user_id: Optional[str] = None
    ) -> np.ndarray:
        """
        안티-노이즈 신호 생성 및 MQTT로 스피커에 전송
        Args:
            reference_data: Reference 마이크 데이터 (노이즈 소스)
            error_data: Error 마이크 데이터 (귀 근처 잔여 노이즈)
            user_id: 사용자 ID
        Returns:
            안티노이즈 신호 (float32, -1.0 ~ 1.0)
        """
        start_time = time.time()

        try:
            
            reference_float = reference_data.astype(np.float32) / 32768.0

            
            anti_noise = -reference_float

            
            
            
            

            
            

            
            

            
            latency_ms = (time.time() - start_time) * 1000

            
            if user_id and mqtt_publisher.is_connected:
                mqtt_publisher.publish_anti_noise(
                    user_id=user_id,
                    anti_noise_data=anti_noise,
                    latency_ms=latency_ms
                )

                
                noise_level = self.calculate_noise_level(reference_data)
                reduction = self.calculate_reduction(reference_data, error_data)
                mqtt_publisher.publish_anc_result(
                    user_id=user_id,
                    noise_level_db=noise_level,
                    reduction_db=reduction,
                    status="active"
                )

            return anti_noise

        except Exception as e:
            logger.error(f" Anti-noise generation error: {e}", exc_info=True)
            
            return np.zeros(len(reference_data), dtype=np.float32)
    
    def calculate_noise_level(self, reference_data: np.ndarray) -> float:
        """
        노이즈 레벨 계산 (dB SPL)

        Args:
            reference_data: Reference 마이크 데이터 (int16)

        Returns:
            노이즈 레벨 (dB)
        """
        try:
            rms = np.sqrt(np.mean(reference_data.astype(np.float32) ** 2))
            db = 20 * np.log10(rms / 32768.0) if rms > 0 else -100
            return float(db)
        except Exception as e:
            logger.error(f" Noise level calculation error: {e}")
            return 0.0

    def calculate_reduction(
        self,
        reference_data: np.ndarray,
        error_data: np.ndarray
    ) -> float:
        """
        노이즈 감소량 계산 (dB)
        Reference 마이크 (원본 소음)와 Error 마이크 (잔여 소음) 비교

        Args:
            reference_data: Reference 마이크 데이터 (원본 소음)
            error_data: Error 마이크 데이터 (ANC 적용 후 잔여 소음)

        Returns:
            노이즈 감소량 (dB)
        """
        try:
            
            ref_rms = np.sqrt(np.mean(reference_data.astype(np.float32) ** 2))
            ref_db = 20 * np.log10(ref_rms / 32768.0) if ref_rms > 0 else -100

            
            error_rms = np.sqrt(np.mean(error_data.astype(np.float32) ** 2))
            error_db = 20 * np.log10(error_rms / 32768.0) if error_rms > 0 else -100

            
            reduction = ref_db - error_db

            return float(reduction)

        except Exception as e:
            logger.error(f" Reduction calculation error: {e}")
            return 0.0