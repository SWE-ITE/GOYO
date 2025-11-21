"""
GOYO AI Server - Main Application
Real-time audio processing and ANC signal generation
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from typing import Dict
import json

from config import settings
from audio_processor import AudioProcessor
from redis_client import RedisClient
from anc_controller import ANCController
from mqtt_publisher import mqtt_publisher

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="GOYO AI Server",
    description="Real-time audio processing and Active Noise Control",
    version="3.5.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
redis_client = RedisClient()
audio_processor = AudioProcessor()
anc_controller = ANCController()

# Active WebSocket connections
active_connections: Dict[str, WebSocket] = {}


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    logger.info("🚀 GOYO AI Server starting...")

    # MQTT Publisher 연결
    try:
        mqtt_publisher.connect()
        logger.info("✅ MQTT Publisher connected")
    except Exception as e:
        logger.error(f"❌ MQTT Publisher connection failed: {e}")

    # Redis 연결
    await redis_client.connect()
    logger.info("✅ Redis connected")

    # Redis Pub/Sub 리스너 시작 (제어 명령용)
    asyncio.create_task(redis_audio_listener())
    logger.info("✅ Redis control listener started")

    # Audio Processor 초기화
    audio_processor.initialize()
    logger.info("✅ Audio Processor initialized")

    logger.info("🎉 GOYO AI Server ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 정리"""
    logger.info("🛑 GOYO AI Server shutting down...")

    # MQTT Publisher 연결 해제
    try:
        mqtt_publisher.disconnect()
        logger.info("✅ MQTT Publisher disconnected")
    except Exception as e:
        logger.error(f"❌ MQTT Publisher disconnect error: {e}")

    await redis_client.disconnect()
    audio_processor.cleanup()
    
    logger.info("✅ Cleanup complete")


async def redis_audio_listener():
    """Redis Pub/Sub으로 오디오 데이터 수신"""
    pubsub = redis_client.client.pubsub()
    
    # 채널 구독
    await pubsub.subscribe(
        "audio:source",
        "audio:reference",
        "anc:control"
    )
    
    logger.info("📡 Listening to Redis channels: audio:source, audio:reference, anc:control")
    
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            
            channel = message["channel"].decode()
            data = json.loads(message["data"])
            
            if channel == "audio:source":
                # Source 마이크 데이터 처리
                await handle_source_audio(data)
                
            elif channel == "audio:reference":
                # Reference 마이크 데이터 처리
                await handle_reference_audio(data)
                
            elif channel == "anc:control":
                # ANC 제어 명령
                await handle_anc_control(data)
                
    except Exception as e:
        logger.error(f"❌ Redis listener error: {e}")


async def handle_source_audio(data: dict):
    """Source 마이크 오디오 처리"""
    try:
        user_id = data.get("user_id")
        audio_chunk = data.get("audio_data")  # base64 encoded
        timestamp = data.get("timestamp")
        
        # Audio Processor에 전달
        audio_processor.process_source(user_id, audio_chunk, timestamp)
        
    except Exception as e:
        logger.error(f"❌ Source audio processing error: {e}")


async def handle_reference_audio(data: dict):
    """Reference 마이크 오디오 처리"""
    try:
        user_id = data.get("user_id")
        audio_chunk = data.get("audio_data")
        timestamp = data.get("timestamp")
        
        # Audio Processor에 전달
        audio_processor.process_reference(user_id, audio_chunk, timestamp)
        
        # 두 마이크 데이터가 모두 준비되면 ANC 처리
        if audio_processor.is_ready(user_id):
            await process_anc(user_id)
        
    except Exception as e:
        logger.error(f"❌ Reference audio processing error: {e}")


async def process_anc(user_id: str):
    """ANC 신호 생성 및 전송"""
    try:
        # 1. 두 마이크 데이터 가져오기
        source_data = audio_processor.get_source_buffer(user_id)
        reference_data = audio_processor.get_reference_buffer(user_id)
        
        # 2. 노이즈 분류 (Phase 5에서 구현 예정)
        # noise_type = noise_classifier.classify(source_data)
        
        # 3. 공간 전달 함수 계산 (Phase 5에서 구현 예정)
        # transfer_function = calculate_transfer_function(source_data, reference_data)
        
        # 4. ANC 신호 생성 (현재는 기본 역위상 신호)
        anti_noise_signal = anc_controller.generate_anti_noise(
            source_data, 
            reference_data
        )
        
        # 5. MQTT로 스피커에 전송
        await publish_to_speaker(user_id, anti_noise_signal)
        
        # 6. 결과를 Backend에 전송 (모니터링용)
        await publish_anc_result(user_id, {
            "timestamp": audio_processor.get_timestamp(),
            "noise_level_db": audio_processor.calculate_noise_level(source_data),
            "reduction_db": -15.2,  # 실제 계산 필요
            "status": "active"
        })
        
    except Exception as e:
        logger.error(f"❌ ANC processing error: {e}")


async def publish_to_speaker(user_id: str, audio_data: bytes):
    """MQTT로 스피커에 안티-노이즈 신호 전송"""
    try:
        # MQTT 토픽: speaker/{user_id}/output
        topic = f"speaker/{user_id}/output"
        
        # Redis에 임시 저장 (MQTT 클라이언트가 가져감)
        await redis_client.set(
            f"mqtt:speaker:{user_id}",
            audio_data,
            ex=1  # 1초 TTL
        )
        
        logger.debug(f"📤 Published to speaker: {len(audio_data)} bytes")
        
    except Exception as e:
        logger.error(f"❌ Speaker publish error: {e}")


async def publish_anc_result(user_id: str, result: dict):
    """ANC 처리 결과를 Backend에 전송"""
    try:
        await redis_client.publish(
            "anc:result",
            json.dumps({
                "user_id": user_id,
                **result
            })
        )
        
    except Exception as e:
        logger.error(f"❌ Result publish error: {e}")


async def handle_anc_control(data: dict):
    """ANC 제어 명령 처리"""
    try:
        user_id = data.get("user_id")
        command = data.get("command")  # "start", "stop", "adjust"
        params = data.get("params", {})
        
        if command == "start":
            anc_controller.start(user_id)
            logger.info(f"▶️  ANC started for user {user_id}")
            
        elif command == "stop":
            anc_controller.stop(user_id)
            logger.info(f"⏹️  ANC stopped for user {user_id}")
            
        elif command == "adjust":
            suppression_level = params.get("suppression_level", 80)
            anc_controller.adjust(user_id, suppression_level)
            logger.info(f"🔧 ANC adjusted: {suppression_level}%")
        
    except Exception as e:
        logger.error(f"❌ ANC control error: {e}")


@app.get("/")
async def root():
    """Health check"""
    return {
        "service": "GOYO AI Server",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
        "redis": redis_client.is_connected(),
        "audio_processor": audio_processor.is_initialized(),
        "active_sessions": len(audio_processor.active_sessions)
    }


@app.websocket("/ws/monitor/{user_id}")
async def websocket_monitor(websocket: WebSocket, user_id: str):
    """
    실시간 모니터링용 WebSocket
    프론트엔드에서 ANC 상태를 실시간으로 확인
    """
    await websocket.accept()
    active_connections[user_id] = websocket
    
    logger.info(f"📱 WebSocket connected: user {user_id}")
    
    try:
        while True:
            # 실시간 상태 전송
            status = audio_processor.get_status(user_id)
            await websocket.send_json(status)
            await asyncio.sleep(0.1)  # 100ms 간격
            
    except WebSocketDisconnect:
        logger.info(f"📱 WebSocket disconnected: user {user_id}")
        del active_connections[user_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )