"""
MQTT Service
라즈베리파이에서 MQTT로 수신한 오디오를 Redis Pub/Sub으로 AI Server에 전달
"""
import json
import logging
from typing import Optional
import paho.mqtt.client as mqtt
from app.config import settings
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)


class MQTTService:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False

    def on_connect(self, client, userdata, flags, rc):
        """MQTT 브로커 연결 시 호출"""
        if rc == 0:
            logger.info("✅ Connected to MQTT Broker")
            self.is_connected = True

            # 모든 오디오 토픽 구독
            client.subscribe("mqtt/audio/source/#", qos=1)
            client.subscribe("mqtt/audio/reference/#", qos=1)
            client.subscribe("mqtt/control/#", qos=1)
            client.subscribe("mqtt/status/#", qos=1)

            logger.info("📡 Subscribed to MQTT topics:")
            logger.info("   - mqtt/audio/source/#")
            logger.info("   - mqtt/audio/reference/#")
            logger.info("   - mqtt/control/#")
            logger.info("   - mqtt/status/#")
        else:
            logger.error(f"❌ Failed to connect to MQTT Broker, return code {rc}")
            self.is_connected = False

    def on_disconnect(self, client, userdata, rc):
        """MQTT 브로커 연결 해제 시 호출"""
        logger.warning(f"⚠️ Disconnected from MQTT Broker (rc: {rc})")
        self.is_connected = False

        if rc != 0:
            logger.info("Attempting to reconnect...")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def on_message(self, client, userdata, msg):
        """MQTT 메시지 수신 시 호출 - Redis Pub/Sub으로 브리지"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))

            # 오디오 데이터 처리
            if "audio/source" in topic:
                # Source 마이크 오디오 → Redis Pub/Sub
                redis_client.publish("audio:source", json.dumps(payload))
                logger.debug(f"📨 Forwarded source audio from {topic} to Redis")

            elif "audio/reference" in topic:
                # Reference 마이크 오디오 → Redis Pub/Sub
                redis_client.publish("audio:reference", json.dumps(payload))
                logger.debug(f"📨 Forwarded reference audio from {topic} to Redis")

            elif "control" in topic:
                # 제어 명령 처리
                logger.info(f"🎛️ Control message received: {topic} - {payload}")
                # TODO: 제어 로직 추가 (필요 시)

            elif "status" in topic:
                # 디바이스 상태 보고
                logger.info(f"📊 Status update: {topic} - {payload}")
                # TODO: 상태 저장 (필요 시)

        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON payload from topic: {msg.topic}")
        except Exception as e:
            logger.error(f"❌ Error processing MQTT message: {e}", exc_info=True)

    def on_log(self, client, userdata, level, buf):
        """MQTT 로그 (디버깅용)"""
        if level == mqtt.MQTT_LOG_ERR:
            logger.error(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_WARNING:
            logger.warning(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_NOTICE or level == mqtt.MQTT_LOG_INFO:
            logger.info(f"MQTT: {buf}")
        else:
            logger.debug(f"MQTT: {buf}")

    def connect(self):
        """MQTT 브로커에 연결"""
        try:
            self.client = mqtt.Client(client_id="goyo-backend", clean_session=False)

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
            self.client.on_log = self.on_log

            # Will 메시지 설정 (비정상 종료 시)
            self.client.will_set(
                "mqtt/status/backend",
                json.dumps({"status": "offline", "timestamp": None}),
                qos=1,
                retain=True
            )

            # 연결
            logger.info(f"Connecting to MQTT Broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}")
            self.client.connect(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                keepalive=60
            )

            # 백그라운드 루프 시작
            self.client.loop_start()

            logger.info("🚀 MQTT Service started")

        except Exception as e:
            logger.error(f"❌ Failed to connect to MQTT Broker: {e}", exc_info=True)
            raise

    def disconnect(self):
        """MQTT 브로커 연결 해제"""
        if self.client:
            # 온라인 상태 메시지 전송
            self.client.publish(
                "mqtt/status/backend",
                json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )

            self.client.loop_stop()
            self.client.disconnect()
            logger.info("🛑 MQTT Service stopped")

    def publish(self, topic: str, payload: dict, qos: int = 1):
        """MQTT 메시지 발행"""
        if not self.is_connected:
            logger.warning("⚠️ MQTT not connected, cannot publish")
            return False

        try:
            result = self.client.publish(
                topic,
                json.dumps(payload),
                qos=qos
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📤 Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"❌ Failed to publish to {topic}: rc={result.rc}")
                return False

        except Exception as e:
            logger.error(f"❌ Error publishing to {topic}: {e}")
            return False


# 싱글톤 인스턴스
mqtt_service = MQTTService()
