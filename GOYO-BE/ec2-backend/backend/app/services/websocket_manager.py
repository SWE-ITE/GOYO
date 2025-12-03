"""
WebSocket Connection Manager
실시간 알림을 위한 WebSocket 연결 관리
"""
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id별로 WebSocket 연결을 관리
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """WebSocket 연결 추가"""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        logger.info(f"✅ WebSocket connected: user_id={user_id}, total={len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        """WebSocket 연결 제거"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            # 해당 user의 연결이 모두 끊어지면 dict에서 제거
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

            logger.info(f"🔌 WebSocket disconnected: user_id={user_id}")

    async def send_personal_message(self, message: dict, user_id: int):
        """특정 사용자에게 메시지 전송"""
        if user_id not in self.active_connections:
            logger.debug(f"No active connections for user_id={user_id}")
            return

        # 해당 user의 모든 연결된 클라이언트에게 전송
        disconnected = []
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
                logger.debug(f"📤 Sent message to user_id={user_id}: {message}")
            except Exception as e:
                logger.error(f"❌ Failed to send message to user_id={user_id}: {e}")
                disconnected.append(connection)

        # 연결이 끊어진 WebSocket 제거
        for connection in disconnected:
            self.disconnect(connection, user_id)

    async def broadcast(self, message: dict):
        """모든 연결된 클라이언트에게 메시지 브로드캐스트"""
        disconnected = []

        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"❌ Failed to broadcast to user_id={user_id}: {e}")
                    disconnected.append((user_id, connection))

        # 연결이 끊어진 WebSocket 제거
        for user_id, connection in disconnected:
            self.disconnect(connection, user_id)

    def get_active_users(self) -> Set[int]:
        """현재 연결된 모든 사용자 ID 반환"""
        return set(self.active_connections.keys())


# 싱글톤 인스턴스
websocket_manager = ConnectionManager()
