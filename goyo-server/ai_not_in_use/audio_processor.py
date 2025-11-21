"""
Audio Processor
Handles audio buffering and synchronization
"""
import numpy as np
import base64
import logging
from typing import Dict, Optional, Tuple
from collections import deque
import time

from config import settings

logger = logging.getLogger(__name__)


class AudioBuffer:
    """오디오 버퍼 관리"""
    
    def __init__(self, max_size: int = 10):
        self.buffer = deque(maxlen=max_size)
        self.timestamps = deque(maxlen=max_size)
    
    def add(self, data: np.ndarray, timestamp: float):
        """버퍼에 데이터 추가"""
        self.buffer.append(data)
        self.timestamps.append(timestamp)
    
    def get_latest(self) -> Optional[np.ndarray]:
        """최신 데이터 조회"""
        return self.buffer[-1] if self.buffer else None
    
    def get_all(self) -> np.ndarray:
        """모든 데이터 병합"""
        if not self.buffer:
            return np.array([])
        return np.concatenate(list(self.buffer))
    
    def clear(self):
        """버퍼 초기화"""
        self.buffer.clear()
        self.timestamps.clear()
    
    def is_empty(self) -> bool:
        """버퍼 비어있는지 확인"""
        return len(self.buffer) == 0
    
    def size(self) -> int:
        """버퍼 크기"""
        return len(self.buffer)


class AudioProcessor:
    """오디오 처리 및 동기화"""
    
    def __init__(self):
        # 사용자별 버퍼 관리
        self.source_buffers: Dict[str, AudioBuffer] = {}
        self.reference_buffers: Dict[str, AudioBuffer] = {}
        
        # 활성 세션
        self.active_sessions = set()
        
        # 초기화 상태
        self._initialized = False
    
    def initialize(self):
        """Audio Processor 초기화"""
        self._initialized = True
        logger.info("✅ Audio Processor initialized")
    
    def cleanup(self):
        """정리"""
        self.source_buffers.clear()
        self.reference_buffers.clear()
        self.active_sessions.clear()
        self._initialized = False
    
    def is_initialized(self) -> bool:
        """초기화 상태 확인"""
        return self._initialized
    
    def _get_or_create_buffers(self, user_id: str) -> Tuple[AudioBuffer, AudioBuffer]:
        """사용자별 버퍼 생성 또는 조회"""
        if user_id not in self.source_buffers:
            self.source_buffers[user_id] = AudioBuffer(settings.MAX_BUFFER_SIZE)
            self.reference_buffers[user_id] = AudioBuffer(settings.MAX_BUFFER_SIZE)
            self.active_sessions.add(user_id)
        
        return self.source_buffers[user_id], self.reference_buffers[user_id]
    
    def process_source(self, user_id: str, audio_data: str, timestamp: float):
        """Source 마이크 데이터 처리"""
        try:
            # Base64 디코딩
            audio_bytes = base64.b64decode(audio_data)
            
            # NumPy 배열로 변환
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # 버퍼에 추가
            source_buffer, _ = self._get_or_create_buffers(user_id)
            source_buffer.add(audio_array, timestamp)
            
            logger.debug(f"✅ Source audio processed: {len(audio_array)} samples")
            
        except Exception as e:
            logger.error(f"❌ Source processing error: {e}")
    
    def process_reference(self, user_id: str, audio_data: str, timestamp: float):
        """Reference 마이크 데이터 처리"""
        try:
            # Base64 디코딩
            audio_bytes = base64.b64decode(audio_data)
            
            # NumPy 배열로 변환
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # 버퍼에 추가
            _, reference_buffer = self._get_or_create_buffers(user_id)
            reference_buffer.add(audio_array, timestamp)
            
            logger.debug(f"✅ Reference audio processed: {len(audio_array)} samples")
            
        except Exception as e:
            logger.error(f"❌ Reference processing error: {e}")
    
    def is_ready(self, user_id: str) -> bool:
        """두 마이크 데이터가 모두 준비되었는지 확인"""
        if user_id not in self.source_buffers:
            return False
        
        source_buffer = self.source_buffers[user_id]
        reference_buffer = self.reference_buffers[user_id]
        
        # 둘 다 최소 1개 이상의 데이터가 있어야 함
        return not source_buffer.is_empty() and not reference_buffer.is_empty()
    
    def get_source_buffer(self, user_id: str) -> Optional[np.ndarray]:
        """Source 버퍼 데이터 조회"""
        if user_id in self.source_buffers:
            return self.source_buffers[user_id].get_latest()
        return None
    
    def get_reference_buffer(self, user_id: str) -> Optional[np.ndarray]:
        """Reference 버퍼 데이터 조회"""
        if user_id in self.reference_buffers:
            return self.reference_buffers[user_id].get_latest()
        return None
    
    def calculate_noise_level(self, audio_data: np.ndarray) -> float:
        """노이즈 레벨 계산 (dB SPL)"""
        try:
            # RMS 계산
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            
            # dB SPL 변환 (참조: 16-bit max)
            if rms > 0:
                db = 20 * np.log10(rms / 32768.0) + 94  # 94 dB SPL reference
                return float(db)
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Noise level calculation error: {e}")
            return 0.0
    
    def get_timestamp(self) -> float:
        """현재 타임스탬프"""
        return time.time()
    
    def get_status(self, user_id: str) -> dict:
        """사용자 오디오 처리 상태"""
        if user_id not in self.source_buffers:
            return {"status": "inactive"}
        
        source_buffer = self.source_buffers[user_id]
        reference_buffer = self.reference_buffers[user_id]
        
        source_data = source_buffer.get_latest()
        reference_data = reference_buffer.get_latest()
        
        return {
            "status": "active",
            "source_buffer_size": source_buffer.size(),
            "reference_buffer_size": reference_buffer.size(),
            "source_noise_level": self.calculate_noise_level(source_data) if source_data is not None else 0,
            "reference_noise_level": self.calculate_noise_level(reference_data) if reference_data is not None else 0,
            "is_ready": self.is_ready(user_id)
        }
    
    def clear_buffers(self, user_id: str):
        """사용자 버퍼 초기화"""
        if user_id in self.source_buffers:
            self.source_buffers[user_id].clear()
        if user_id in self.reference_buffers:
            self.reference_buffers[user_id].clear()