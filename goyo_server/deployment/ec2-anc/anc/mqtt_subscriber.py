"""
MQTT Subscriber for AI Server
MQTT Broker에서 직접 오디오 데이터 구독 (Redis Pub/Sub 대체)
"""
import json
import logging
import time
from typing import Optional, Callable
import paho.mqtt.client as mqtt

from config import settings

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    """MQTT 오디오 데이터 구독"""

    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False

        # 콜백 핸들러
        self.on_reference_audio: Optional[Callable] = None
        self.on_error_audio: Optional[Callable] = None
        self.on_control: Optional[Callable] = None

    def on_connect(self, client, userdata, flags, rc):
        """MQTT 브로커 연결 시 호출"""
        if rc == 0:
            logger.info("✅ ANC Server connected to MQTT Broker")
            self.is_connected = True

            # 오디오 토픽 구독
            client.subscribe("mqtt/audio/reference/#", qos=1)
            client.subscribe("mqtt/audio/error/#", qos=1)
            client.subscribe("mqtt/control/anc/#", qos=1)

            logger.info("📡 Subscribed to MQTT topics:")
            logger.info("   - mqtt/audio/reference/#")
            logger.info("   - mqtt/audio/error/#")
            logger.info("   - mqtt/control/anc/#")
        else:
            logger.error(f"❌ Failed to connect to MQTT Broker, return code {rc}")
            self.is_connected = False

    def on_disconnect(self, client, userdata, rc):
        """MQTT 브로커 연결 해제 시 호출"""
        logger.warning(f"⚠️ ANC Server disconnected from MQTT Broker (rc: {rc})")
        self.is_connected = False

        if rc != 0:
            logger.info("Attempting to reconnect...")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def on_message(self, client, userdata, msg):
        """MQTT 메시지 수신"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))

            # Reference 마이크 데이터
            if "audio/reference" in topic:
                if self.on_reference_audio:
                    self.on_reference_audio(payload)
                else:
                    logger.warning("No handler for reference audio")

            # Error 마이크 데이터
            elif "audio/error" in topic:
                if self.on_error_audio:
                    self.on_error_audio(payload)
                else:
                    logger.warning("No handler for error audio")

            # 제어 명령
            elif "control/anc" in topic:
                if self.on_control:
                    self.on_control(payload)
                else:
                    logger.info(f"🎛️ Control message: {payload}")

        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON from topic: {msg.topic}")
        except Exception as e:
            logger.error(f"❌ Error processing MQTT message: {e}", exc_info=True)

    def connect(self):
        """MQTT 브로커에 연결"""
        try:
            self.client = mqtt.Client(
                client_id="goyo-anc-server-subscriber",
                clean_session=False
            )

            # 인증 설정
            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                self.client.username_pw_set(
                    settings.MQTT_USERNAME,
                    settings.MQTT_PASSWORD
                )

            # 콜백 등록
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message

            # Will 메시지 설정
            self.client.will_set(
                "mqtt/status/anc-server/subscriber",
                json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )

            # 연결
            logger.info(
                f"Connecting to MQTT Broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}"
            )
            self.client.connect(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                keepalive=60
            )

            # 백그라운드 루프 시작
            self.client.loop_start()

            # 연결 대기 (최대 5초)
            wait_count = 0
            while not self.is_connected and wait_count < 50:
                time.sleep(0.1)
                wait_count += 1

            if self.is_connected:
                logger.info("🚀 MQTT Subscriber started")
                # 온라인 상태 발행
                self.publish_status("online")
            else:
                logger.error("❌ MQTT connection timeout")

        except Exception as e:
            logger.error(f"❌ Failed to connect to MQTT Broker: {e}", exc_info=True)
            raise

    def disconnect(self):
        """MQTT 브로커 연결 해제"""
        if self.client:
            self.publish_status("offline")
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("🛑 MQTT Subscriber stopped")

    def publish_status(self, status: str):
        """ANC Server 상태 발행"""
        if self.client:
            try:
                self.client.publish(
                    "mqtt/status/anc-server/subscriber",
                    json.dumps({
                        "status": status,
                        "timestamp": time.time()
                    }),
                    qos=1,
                    retain=True
                )
                logger.debug(f"📊 Published status: {status}")
            except Exception as e:
                logger.error(f"Error publishing status: {e}")

    def set_reference_handler(self, handler: Callable):
        """Reference 마이크 핸들러 등록"""
        self.on_reference_audio = handler

    def set_error_handler(self, handler: Callable):
        """Error 마이크 핸들러 등록"""
        self.on_error_audio = handler

    def set_control_handler(self, handler: Callable):
        """제어 명령 핸들러 등록"""
        self.on_control = handler


# 싱글톤 인스턴스
mqtt_subscriber = MQTTSubscriber()
