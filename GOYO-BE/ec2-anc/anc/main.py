"""
GOYO ANC Server - Main Application
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
from anc_controller import ANCController
from mqtt_publisher import mqtt_publisher
from mqtt_subscriber import mqtt_subscriber

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GOYO ANC Server",
    description="Real-time audio processing and Active Noise Control",
    version="3.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

audio_processor = AudioProcessor()
anc_controller = ANCController()
active_connections: Dict[str, WebSocket] = {}
main_event_loop = None


@app.on_event("startup")
async def startup_event():
    global main_event_loop
    main_event_loop = asyncio.get_event_loop()
    logger.info("GOYO ANC Server starting...")

    try:
        mqtt_publisher.connect()
        logger.info("MQTT Publisher connected")
    except Exception as e:
        logger.error(f"MQTT Publisher connection failed: {e}")

    try:
        mqtt_subscriber.set_reference_handler(handle_reference_audio)
        mqtt_subscriber.set_error_handler(handle_error_audio)
        mqtt_subscriber.set_control_handler(handle_anc_control)
        mqtt_subscriber.connect()
        logger.info("MQTT Subscriber connected")
    except Exception as e:
        logger.error(f"MQTT Subscriber connection failed: {e}")

    audio_processor.initialize()
    logger.info("Audio Processor initialized")
    logger.info("GOYO ANC Server ready!")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("GOYO ANC Server shutting down...")

    try:
        mqtt_publisher.disconnect()
        logger.info("MQTT Publisher disconnected")
    except Exception as e:
        logger.error(f"MQTT Publisher disconnect error: {e}")

    try:
        mqtt_subscriber.disconnect()
        logger.info("MQTT Subscriber disconnected")
    except Exception as e:
        logger.error(f"MQTT Subscriber disconnect error: {e}")

    audio_processor.cleanup()
    logger.info("Cleanup complete")


def handle_reference_audio(data: dict):
    try:
        user_id = data.get("user_id")
        audio_chunk = data.get("audio_data")
        timestamp = data.get("timestamp")

        audio_processor.process_reference(user_id, audio_chunk, timestamp)
        logger.debug(f"Reference audio processed for user {user_id}")

    except Exception as e:
        logger.error(f"Reference audio processing error: {e}")


def handle_error_audio(data: dict):
    try:
        user_id = data.get("user_id")
        audio_chunk = data.get("audio_data")
        timestamp = data.get("timestamp")

        audio_processor.process_error(user_id, audio_chunk, timestamp)

        if audio_processor.is_ready(user_id):
            if main_event_loop:
                asyncio.run_coroutine_threadsafe(
                    process_anc(user_id),
                    main_event_loop
                )

        logger.debug(f"Error audio processed for user {user_id}")

    except Exception as e:
        logger.error(f"Error audio processing error: {e}")


async def process_anc(user_id: str):
    try:
        reference_data = audio_processor.get_reference_buffer(user_id)
        error_data = audio_processor.get_error_buffer(user_id)

        anti_noise_signal = anc_controller.generate_anti_noise(
            reference_data,
            error_data,
            user_id
        )

        await publish_to_speaker(user_id, anti_noise_signal)

    except Exception as e:
        logger.error(f"ANC processing error: {e}")


async def publish_to_speaker(user_id: str, audio_data):
    try:
        success = mqtt_publisher.publish_anti_noise(user_id, audio_data)

        if success:
            logger.debug(f"Published anti-noise to speaker for user {user_id}")
        else:
            logger.warning(f"Failed to publish anti-noise for user {user_id}")

    except Exception as e:
        logger.error(f"Speaker publish error: {e}")


def handle_anc_control(data: dict):
    try:
        user_id = data.get("user_id")
        command = data.get("command")
        device_type = data.get("device_type", "unknown")

        if command == "start":
            logger.info(f"ANC START command received")
            logger.info(f"   User: {user_id}, Device: {device_type}")

            anc_controller.start(user_id)

            if hasattr(audio_processor, 'activate_session'):
                audio_processor.activate_session(user_id)

            logger.info(f"ANC pipeline activated for user {user_id}")

        elif command == "stop":
            logger.info(f"ANC STOP command received for user {user_id}")
            anc_controller.stop(user_id)

            if hasattr(audio_processor, 'deactivate_session'):
                audio_processor.deactivate_session(user_id)

    except Exception as e:
        logger.error(f"ANC control error: {e}")


@app.get("/")
async def root():
    return {
        "service": "GOYO ANC Server",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mqtt_subscriber": mqtt_subscriber.is_connected,
        "mqtt_publisher": mqtt_publisher.is_connected,
        "audio_processor": audio_processor.is_initialized(),
        "active_sessions": len(audio_processor.active_sessions)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )