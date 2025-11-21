"""
Audio Streaming Service
USB 마이크에서 오디오 캡처하고 Redis Pub/Sub으로 AI 서버에 전송
"""
import asyncio
import pyaudio
import numpy as np
import logging
import json
import base64
import time
from typing import Optional, Dict
from threading import Thread

from app.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class AudioStreamingService:
    """오디오 캡처 및 스트리밍 서비스"""

    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.sample_rate = 44100
        self.chunk_size = 4096  # 프레임당 샘플 수
        self.format = pyaudio.paInt16

        # 스트리밍 상태
        self.active_sessions: Dict[str, dict] = {}  # user_id -> session info
        self.running = False

    def start_streaming(
        self,
        user_id: str,
        source_device_index: int,
        reference_device_index: int
    ):
        """
        오디오 스트리밍 시작

        Args:
            user_id: 사용자 ID
            source_device_index: Source 마이크 디바이스 인덱스
            reference_device_index: Reference 마이크 디바이스 인덱스
        """
        if user_id in self.active_sessions:
            logger.warning(f"User {user_id} already has an active session")
            return

        # Source 스트림 열기
        source_stream = self.p.open(
            format=self.format,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=source_device_index,
            frames_per_buffer=self.chunk_size,
            stream_callback=None
        )

        # Reference 스트림 열기
        reference_stream = self.p.open(
            format=self.format,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=reference_device_index,
            frames_per_buffer=self.chunk_size,
            stream_callback=None
        )

        # 세션 정보 저장
        self.active_sessions[user_id] = {
            "source_stream": source_stream,
            "reference_stream": reference_stream,
            "source_device_index": source_device_index,
            "reference_device_index": reference_device_index,
            "running": True
        }

        # 백그라운드 스레드에서 오디오 캡처 시작
        thread = Thread(
            target=self._streaming_loop,
            args=(user_id,),
            daemon=True
        )
        thread.start()

        logger.info(f"✅ Audio streaming started for user {user_id}")
        logger.info(f"   Source device: {source_device_index}")
        logger.info(f"   Reference device: {reference_device_index}")

    def _streaming_loop(self, user_id: str):
        """오디오 캡처 및 전송 루프 (별도 스레드)"""
        session = self.active_sessions.get(user_id)
        if not session:
            return

        source_stream = session["source_stream"]
        reference_stream = session["reference_stream"]

        logger.info(f"🎤 Starting audio capture loop for user {user_id}")

        try:
            while session["running"]:
                # 1. Source 마이크에서 오디오 읽기
                try:
                    source_data = source_stream.read(
                        self.chunk_size,
                        exception_on_overflow=False
                    )
                except Exception as e:
                    logger.error(f"❌ Source mic read error: {e}")
                    continue

                # 2. Reference 마이크에서 오디오 읽기
                try:
                    reference_data = reference_stream.read(
                        self.chunk_size,
                        exception_on_overflow=False
                    )
                except Exception as e:
                    logger.error(f"❌ Reference mic read error: {e}")
                    continue

                # 3. Base64 인코딩
                source_base64 = base64.b64encode(source_data).decode('utf-8')
                reference_base64 = base64.b64encode(reference_data).decode('utf-8')

                # 4. 타임스탬프
                timestamp = time.time()

                # 5. Redis Pub/Sub으로 전송 (비동기)
                asyncio.run(self._publish_audio(
                    user_id,
                    source_base64,
                    reference_base64,
                    timestamp
                ))

        except Exception as e:
            logger.error(f"❌ Streaming loop error for user {user_id}: {e}")

        finally:
            logger.info(f"🛑 Audio capture loop stopped for user {user_id}")

    async def _publish_audio(
        self,
        user_id: str,
        source_base64: str,
        reference_base64: str,
        timestamp: float
    ):
        """Redis Pub/Sub으로 오디오 데이터 전송"""
        try:
            redis_client = await get_redis_client()

            # Source 채널에 전송
            await redis_client.publish(
                "audio:source",
                json.dumps({
                    "user_id": user_id,
                    "audio_data": source_base64,
                    "timestamp": timestamp,
                    "sample_rate": self.sample_rate,
                    "channels": 1
                })
            )

            # Reference 채널에 전송
            await redis_client.publish(
                "audio:reference",
                json.dumps({
                    "user_id": user_id,
                    "audio_data": reference_base64,
                    "timestamp": timestamp,
                    "sample_rate": self.sample_rate,
                    "channels": 1
                })
            )

        except Exception as e:
            logger.error(f"❌ Audio publish error: {e}")

    def stop_streaming(self, user_id: str):
        """오디오 스트리밍 중지"""
        session = self.active_sessions.get(user_id)
        if not session:
            logger.warning(f"No active session for user {user_id}")
            return

        # 스트리밍 중지
        session["running"] = False

        # 스트림 닫기
        try:
            session["source_stream"].stop_stream()
            session["source_stream"].close()
            session["reference_stream"].stop_stream()
            session["reference_stream"].close()
        except Exception as e:
            logger.error(f"❌ Stream close error: {e}")

        # 세션 삭제
        del self.active_sessions[user_id]

        logger.info(f"✅ Audio streaming stopped for user {user_id}")

    def is_streaming(self, user_id: str) -> bool:
        """스트리밍 상태 확인"""
        return user_id in self.active_sessions

    def get_session_info(self, user_id: str) -> Optional[dict]:
        """세션 정보 조회"""
        return self.active_sessions.get(user_id)

    def cleanup(self):
        """모든 스트림 정리"""
        for user_id in list(self.active_sessions.keys()):
            self.stop_streaming(user_id)

        self.p.terminate()
        logger.info("🧹 Audio streaming service cleaned up")


# Global instance
audio_streaming_service = AudioStreamingService()
