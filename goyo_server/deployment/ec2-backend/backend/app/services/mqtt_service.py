"""
MQTT Service
MQTT 메시지 모니터링 및 로깅 (AI Server가 직접 구독)
"""
import json
import logging
import asyncio
from typing import Optional
from datetime import datetime
import paho.mqtt.client as mqtt
from app.config import settings

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

            # 상태 및 모니터링 토픽 구독
            client.subscribe("mqtt/status/#", qos=1)
            client.subscribe("mqtt/anc/result/#", qos=0)

            # 소음 감지 토픽 구독 (실시간 알림용)
            client.subscribe("mqtt/noise/detected/#", qos=1)
            client.subscribe("mqtt/noise/stopped/#", qos=1)

            logger.info("📡 Subscribed to MQTT topics:")
            logger.info("   - mqtt/status/#")
            logger.info("   - mqtt/anc/result/#")
            logger.info("   - mqtt/noise/detected/#")
            logger.info("   - mqtt/noise/stopped/#")
            logger.info("ℹ️  Audio topics are handled directly by AI Server")
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
        """MQTT 메시지 수신 시 호출 - 로깅 및 실시간 알림"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))

            # 상태 메시지 로깅
            if "status" in topic:
                # 디바이스 상태 보고
                logger.info(f"📊 Status update: {topic} - {payload}")

            elif "anc/result" in topic:
                # ANC 처리 결과 (모니터링용)
                logger.debug(f"📈 ANC result: {topic} - {payload}")

            elif "noise/detected" in topic:
                # 소음 감지 - WebSocket으로 실시간 알림
                logger.info(f"🔊 Noise detected: {topic} - {payload}")
                self._handle_noise_detected(payload)

            elif "noise/stopped" in topic:
                # 소음 종료 - WebSocket으로 실시간 알림
                logger.info(f"🔇 Noise stopped: {topic} - {payload}")
                self._handle_noise_stopped(payload)

            else:
                logger.debug(f"📨 MQTT message: {topic}")

        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON payload from topic: {msg.topic}")
        except Exception as e:
            logger.error(f"❌ Error processing MQTT message: {e}", exc_info=True)

    def _handle_noise_detected(self, payload: dict):
        """소음 감지 처리 - DB 업데이트 및 WebSocket 알림"""
        try:
            user_id = payload.get("user_id")
            appliance_name = payload.get("appliance_name")

            if not user_id or not appliance_name:
                logger.warning(f"⚠️ Invalid noise detected payload: {payload}")
                return

            # DB 업데이트
            from app.database import SessionLocal
            from app.models.appliance import Appliance

            db = SessionLocal()
            try:
                appliance = db.query(Appliance).filter(
                    Appliance.user_id == user_id,
                    Appliance.appliance_name == appliance_name
                ).first()

                if appliance:
                    appliance.is_noise_active = True
                    db.commit()
                    db.refresh(appliance)

                    # WebSocket으로 실시간 알림
                    self._send_websocket_notification(
                        user_id=user_id,
                        notification_type="appliance_noise_detected",
                        data={
                            "appliance_id": appliance.id,
                            "appliance_name": appliance.appliance_name,
                            "is_noise_active": True,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    logger.info(f"✅ Appliance {appliance_name} marked as active for user {user_id}")
                else:
                    logger.warning(f"⚠️ Appliance {appliance_name} not found for user {user_id}")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"❌ Error handling noise detected: {e}", exc_info=True)

    def _handle_noise_stopped(self, payload: dict):
        """소음 종료 처리 - DB 업데이트 및 WebSocket 알림"""
        try:
            user_id = payload.get("user_id")
            appliance_name = payload.get("appliance_name")

            if not user_id or not appliance_name:
                logger.warning(f"⚠️ Invalid noise stopped payload: {payload}")
                return

            # DB 업데이트
            from app.database import SessionLocal
            from app.models.appliance import Appliance

            db = SessionLocal()
            try:
                appliance = db.query(Appliance).filter(
                    Appliance.user_id == user_id,
                    Appliance.appliance_name == appliance_name
                ).first()

                if appliance:
                    appliance.is_noise_active = False
                    db.commit()
                    db.refresh(appliance)

                    # WebSocket으로 실시간 알림
                    self._send_websocket_notification(
                        user_id=user_id,
                        notification_type="appliance_noise_stopped",
                        data={
                            "appliance_id": appliance.id,
                            "appliance_name": appliance.appliance_name,
                            "is_noise_active": False,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    logger.info(f"✅ Appliance {appliance_name} marked as inactive for user {user_id}")
                else:
                    logger.warning(f"⚠️ Appliance {appliance_name} not found for user {user_id}")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"❌ Error handling noise stopped: {e}", exc_info=True)

    def _send_websocket_notification(self, user_id: int, notification_type: str, data: dict):
        """WebSocket으로 알림 전송 (비동기 처리)"""
        try:
            from app.services.websocket_manager import websocket_manager

            # asyncio 이벤트 루프에서 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                websocket_manager.send_personal_message(
                    message={
                        "type": notification_type,
                        "data": data
                    },
                    user_id=user_id
                )
            )
            loop.close()

        except Exception as e:
            logger.error(f"❌ Error sending WebSocket notification: {e}", exc_info=True)

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
