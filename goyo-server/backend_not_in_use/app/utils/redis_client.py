import redis.asyncio as redis
from app.config import settings
from typing import Optional
import json

class RedisClient:
    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Redis 연결"""
        if self.client is None:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=False)

    async def disconnect(self):
        """Redis 연결 종료"""
        if self.client:
            await self.client.close()

    async def publish(self, channel: str, message: str):
        """메시지 발행"""
        if self.client is None:
            await self.connect()
        await self.client.publish(channel, message)

    async def set_device_status(self, device_id: str, status: dict, expire: int = 300):
        '''디바이스 상태를 Redis에 저장 (5분 TTL)'''
        if self.client is None:
            await self.connect()
        key = f"device:status:{device_id}"
        await self.client.setex(key, expire, json.dumps(status))

    async def get_device_status(self, device_id: str) -> Optional[dict]:
        '''디바이스 상태 조회'''
        if self.client is None:
            await self.connect()
        key = f"device:status:{device_id}"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def delete_device_status(self, device_id: str):
        '''디바이스 상태 삭제'''
        if self.client is None:
            await self.connect()
        key = f"device:status:{device_id}"
        await self.client.delete(key)

    async def set_audio_buffer(self, mic_type: str, audio_data: bytes, expire: int = 1):
        '''실시간 오디오 버퍼 저장 (1초 TTL)'''
        if self.client is None:
            await self.connect()
        key = f"audio:buffer:{mic_type}"  # source or reference
        await self.client.setex(key, expire, audio_data)

    async def get_audio_buffer(self, mic_type: str) -> Optional[bytes]:
        '''오디오 버퍼 조회'''
        if self.client is None:
            await self.connect()
        key = f"audio:buffer:{mic_type}"
        return await self.client.get(key)

    async def set_user_session(self, user_id: int, session_data: dict, expire: int = 3600):
        '''사용자 세션 저장 (1시간 TTL)'''
        if self.client is None:
            await self.connect()
        key = f"user:session:{user_id}"
        await self.client.setex(key, expire, json.dumps(session_data))

    async def get_user_session(self, user_id: int) -> Optional[dict]:
        '''사용자 세션 조회'''
        if self.client is None:
            await self.connect()
        key = f"user:session:{user_id}"
        data = await self.client.get(key)
        return json.loads(data) if data else None

# Global instance
_redis_client = RedisClient()

async def get_redis_client() -> RedisClient:
    """Redis 클라이언트 싱글톤 반환"""
    if _redis_client.client is None:
        await _redis_client.connect()
    return _redis_client

# Backward compatibility
redis_client = _redis_client