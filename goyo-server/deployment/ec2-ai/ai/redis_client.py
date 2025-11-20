"""
Redis Client for AI Server
Handles Pub/Sub communication with Backend
"""
import redis.asyncio as redis
import logging
from typing import Optional, Any
import json

from config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """AI 서버용 Redis 클라이언트"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self):
        """Redis 연결"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=False  # bytes 처리 위해 False
            )
            
            # 연결 테스트
            await self.client.ping()
            self._connected = True
            
            logger.info(f"✅ Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Redis 연결 종료"""
        if self.client:
            await self.client.close()
            self._connected = False
            logger.info("🔌 Redis disconnected")
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._connected
    
    async def publish(self, channel: str, message: Any):
        """메시지 발행"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            
            await self.client.publish(channel, message)
            logger.debug(f"📤 Published to {channel}")
            
        except Exception as e:
            logger.error(f"❌ Publish error: {e}")
    
    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        """값 저장"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            await self.client.set(key, value, ex=ex)
            
        except Exception as e:
            logger.error(f"❌ Set error: {e}")
    
    async def get(self, key: str) -> Optional[Any]:
        """값 조회"""
        try:
            value = await self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            return None
            
        except Exception as e:
            logger.error(f"❌ Get error: {e}")
            return None
    
    async def delete(self, key: str):
        """키 삭제"""
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"❌ Delete error: {e}")
    
    async def exists(self, key: str) -> bool:
        """키 존재 확인"""
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"❌ Exists error: {e}")
            return False