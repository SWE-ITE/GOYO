"""
WebSocket API
실시간 알림 엔드포인트
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from app.services.websocket_manager import websocket_manager
from app.utils.security import verify_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ws", tags=["WebSocket"])


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token")
):
    """
    실시간 알림을 위한 WebSocket 엔드포인트

    연결 방법:
    ws://server/api/ws/notifications?token=YOUR_JWT_TOKEN

    수신 메시지 형식:
    {
        "type": "appliance_noise_detected" | "appliance_noise_stopped",
        "data": {
            "appliance_id": 1,
            "appliance_name": "선풍기",
            "is_noise_active": true,
            "timestamp": "2025-11-27T12:00:00"
        }
    }
    """
    user_id = None

    try:
        # JWT 토큰으로 사용자 인증
        payload = verify_access_token(token)
        email = payload.get("sub")

        if not email:
            await websocket.close(code=1008, reason="Invalid token")
            return

        # 이메일로 user_id를 조회해야 하지만, 간단하게 하기 위해 payload에서 가져옴
        # 실제로는 DB에서 user_id를 조회해야 함
        from app.database import get_db
        from app.models.user import User

        db = next(get_db())
        user = db.query(User).filter(User.email == email).first()

        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        user_id = user.id

        # WebSocket 연결 수락 및 등록
        await websocket_manager.connect(websocket, user_id)

        # 연결 성공 메시지 전송
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "user_id": user_id,
                "message": "Connected to GOYO real-time notifications"
            }
        })

        # 연결 유지 (클라이언트로부터 메시지를 기다림)
        while True:
            # 클라이언트로부터 메시지 수신 (keepalive 등)
            data = await websocket.receive_text()
            logger.debug(f"Received from client (user_id={user_id}): {data}")

            # Ping-Pong으로 연결 유지 확인
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user_id={user_id}")
        if user_id:
            websocket_manager.disconnect(websocket, user_id)

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        if user_id:
            websocket_manager.disconnect(websocket, user_id)
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
