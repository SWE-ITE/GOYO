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
        # 사용자별 ANC 상태
        self.active_users: Dict[str, bool] = {}
        self.suppression_levels: Dict[str, int] = {}
    
    def start(self, user_id: str):
        """ANC 시작"""
        self.active_users[user_id] = True
        if user_id not in self.suppression_levels:
            self.suppression_levels[user_id] = settings.DEFAULT_SUPPRESSION_LEVEL
        logger.info(f"▶️  ANC started for user {user_id}")
    
    def stop(self, user_id: str):
        """ANC 중지"""
        self.active_users[user_id] = False
        logger.info(f"⏹️  ANC stopped for user {user_id}")
    
    def adjust(self, user_id: str, suppression_level: int):
        """억제 강도 조절"""
        if 0 <= suppression_level <= 100:
            self.suppression_levels[user_id] = suppression_level
            logger.info(f"🔧 ANC adjusted: {suppression_level}% for user {user_id}")
    
    def is_active(self, user_id: str) -> bool:
        """ANC 활성 상태 확인"""
        return self.active_users.get(user_id, False)
    
    def generate_anti_noise(
        self,
        source_data: np.ndarray,
        reference_data: np.ndarray,
        user_id: Optional[str] = None
    ) -> np.ndarray:
        """
        안티-노이즈 신호 생성 및 MQTT로 스피커에 전송

        Phase 3.5: 기본 역위상 신호
        Phase 5: FxLMS 적응 필터, 공간 전달 함수 적용

        Returns:
            안티노이즈 신호 (float32, -1.0 ~ 1.0)
        """
        start_time = time.time()

        try:
            # 억제 강도 적용
            suppression = self.suppression_levels.get(user_id, 80) / 100.0

            # Int16 → Float32 변환
            source_float = source_data.astype(np.float32) / 32768.0

            # 기본 역위상 신호 생성 (180도 위상 반전)
            anti_noise = -source_float * suppression

            # Phase 5에서 구현 예정:
            # 1. 공간 전달 함수 적용
            # transfer_function = self.calculate_transfer_function(source_data, reference_data)
            # anti_noise = self.apply_transfer_function(anti_noise, transfer_function)

            # 2. FxLMS 적응 필터
            # anti_noise = self.fxlms_filter(anti_noise, reference_data)

            # 3. 딜레이 보상
            # anti_noise = self.compensate_delay(anti_noise, estimated_delay)

            # 레이턴시 계산
            latency_ms = (time.time() - start_time) * 1000

            # MQTT로 스피커에 안티노이즈 전송
            if user_id and mqtt_publisher.is_connected:
                mqtt_publisher.publish_anti_noise(
                    user_id=user_id,
                    anti_noise_data=anti_noise,
                    latency_ms=latency_ms
                )

                # ANC 결과도 Backend에 전송 (모니터링용)
                noise_level = self.calculate_noise_level(source_data)
                reduction = self.calculate_reduction(source_data, reference_data)
                mqtt_publisher.publish_anc_result(
                    user_id=user_id,
                    noise_level_db=noise_level,
                    reduction_db=reduction,
                    status="active"
                )

            return anti_noise

        except Exception as e:
            logger.error(f"❌ Anti-noise generation error: {e}", exc_info=True)
            # 에러 시 무음 반환
            return np.zeros(len(source_data), dtype=np.float32)
    
    def calculate_noise_level(self, source_data: np.ndarray) -> float:
        """
        노이즈 레벨 계산 (dB SPL)

        Args:
            source_data: Source 마이크 데이터 (int16)

        Returns:
            노이즈 레벨 (dB)
        """
        try:
            rms = np.sqrt(np.mean(source_data.astype(np.float32) ** 2))
            db = 20 * np.log10(rms / 32768.0) if rms > 0 else -100
            return float(db)
        except Exception as e:
            logger.error(f"❌ Noise level calculation error: {e}")
            return 0.0

    def calculate_reduction(
        self,
        source_data: np.ndarray,
        reference_data: np.ndarray
    ) -> float:
        """
        노이즈 감소량 계산 (dB)
        Phase 5에서 정확한 측정 구현
        """
        try:
            # Source 레벨
            source_rms = np.sqrt(np.mean(source_data.astype(np.float32) ** 2))
            source_db = 20 * np.log10(source_rms / 32768.0) if source_rms > 0 else -100

            # Reference 레벨 (ANC 적용 후)
            ref_rms = np.sqrt(np.mean(reference_data.astype(np.float32) ** 2))
            ref_db = 20 * np.log10(ref_rms / 32768.0) if ref_rms > 0 else -100

            # 감소량
            reduction = source_db - ref_db

            return float(reduction)

        except Exception as e:
            logger.error(f"❌ Reduction calculation error: {e}")
            return 0.0