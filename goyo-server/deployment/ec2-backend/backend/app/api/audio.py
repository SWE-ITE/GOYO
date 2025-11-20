"""
Audio Control API
USB 마이크에서 오디오 캡처하고 Redis Pub/Sub으로 AI 서버에 전송
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
import asyncio
import logging
import json

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.utils.redis_client import get_redis_client
from app.models.user import User
from app.models.device import Device
from app.services.audio_streaming_service import audio_streaming_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/start")
async def start_audio_stream(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    ANC 시작: USB 마이크에서 오디오 캡처 시작
    Backend가 PyAudio로 마이크 입력을 받아 Redis Pub/Sub으로 AI 서버에 전송
    """
    user_id = str(current_user.id)

    # 이미 스트리밍 중인지 확인
    if audio_streaming_service.is_streaming(user_id):
        return {
            "success": False,
            "error": "Audio streaming already active for this user"
        }

    # 디바이스 구성 확인
    devices = db.query(Device).filter(Device.user_id == current_user.id).all()

    source_device = next((d for d in devices if d.device_type == "microphone_source"), None)
    reference_device = next((d for d in devices if d.device_type == "microphone_reference"), None)
    speaker = next((d for d in devices if d.device_type == "speaker"), None)

    if not all([source_device, reference_device, speaker]):
        raise HTTPException(
            status_code=400,
            detail="Device setup incomplete. Please pair source mic, reference mic, and speaker."
        )

    # Device ID에서 PyAudio 인덱스 추출
    # 예: "USB_MIC_0" -> 0
    try:
        source_index = int(source_device.device_id.split("_")[-1])
        reference_index = int(reference_device.device_id.split("_")[-1])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=500,
            detail="Invalid device ID format"
        )

    # 오디오 스트리밍 시작 (백그라운드 스레드)
    try:
        audio_streaming_service.start_streaming(
            user_id=user_id,
            source_device_index=source_index,
            reference_device_index=reference_index
        )
    except Exception as e:
        logger.error(f"Failed to start audio streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start audio streaming: {str(e)}"
        )

    # Redis에 ANC 시작 명령 전송 (AI Server에 알림)
    redis_client = await get_redis_client()
    await redis_client.publish(
        "anc:control",
        json.dumps({
            "user_id": user_id,
            "command": "start",
            "params": {
                "suppression_level": current_user.anc_suppression_level
            }
        })
    )

    logger.info(f"✅ ANC started for user {user_id}")

    return {
        "success": True,
        "message": "Audio streaming started",
        "source_device": source_device.device_name,
        "reference_device": reference_device.device_name,
        "speaker": speaker.device_name,
        "source_device_index": source_index,
        "reference_device_index": reference_index
    }


@router.post("/stop")
async def stop_audio_stream(
    current_user: User = Depends(get_current_user)
):
    """ANC 중지: USB 마이크 오디오 캡처 중지"""
    user_id = str(current_user.id)

    # 스트리밍 중인지 확인
    if not audio_streaming_service.is_streaming(user_id):
        return {
            "success": False,
            "error": "No active audio streaming for this user"
        }

    # 오디오 스트리밍 중지
    try:
        audio_streaming_service.stop_streaming(user_id)
    except Exception as e:
        logger.error(f"Failed to stop audio streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop audio streaming: {str(e)}"
        )

    # Redis에 ANC 중지 명령 전송 (AI Server에 알림)
    redis_client = await get_redis_client()
    await redis_client.publish(
        "anc:control",
        json.dumps({
            "user_id": user_id,
            "command": "stop"
        })
    )

    logger.info(f"✅ ANC stopped for user {user_id}")

    return {
        "success": True,
        "message": "Audio streaming stopped"
    }


@router.websocket("/ws/monitor")
async def monitor_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    모니터링용 WebSocket
    AI Server로부터 받은 ANC 결과를 클라이언트에 전송
    """
    await websocket.accept()
    
    try:
        # 첫 메시지로 user_id 받기
        auth_message = await websocket.receive_json()
        user_id = auth_message.get("user_id")  # TODO: JWT 검증
        
        logger.info(f"📊 Monitor WebSocket connected: user {user_id}")
        
        # Redis Pub/Sub으로 ANC 결과 수신
        redis_client = await get_redis_client()
        pubsub = redis_client.client.pubsub()
        await pubsub.subscribe("anc:result")
        
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            
            data = json.loads(message["data"])
            
            # 해당 사용자 데이터만 전송
            if data.get("user_id") == str(user_id):
                await websocket.send_json({
                    "timestamp": data.get("timestamp"),
                    "noise_level_db": data.get("noise_level_db"),
                    "reduction_db": data.get("reduction_db"),
                    "status": data.get("status")
                })
    
    except WebSocketDisconnect:
        logger.info(f"📊 Monitor WebSocket disconnected: user {user_id}")
    
    except Exception as e:
        logger.error(f"❌ Monitor WebSocket error: {e}")
        await websocket.close()