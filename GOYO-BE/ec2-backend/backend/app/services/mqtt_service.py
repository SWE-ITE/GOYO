"""
MQTT Service
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
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            self.is_connected = True

            client.subscribe("mqtt/status/")
            client.subscribe("mqtt/anc/result/")
            client.subscribe("mqtt/noise/detected/")
            client.subscribe("mqtt/noise/stopped/")

            logger.info("Subscribed to MQTT topics:")
            logger.info("   - mqtt/status/")
            logger.info("   - mqtt/anc/result/")
            logger.info("   - mqtt/noise/detected/")
            logger.info("   - mqtt/noise/stopped/")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")
            self.is_connected = False

    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT Broker (rc: {rc})")
        self.is_connected = False

        if rc != 0:
            logger.info("Attempting to reconnect...")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))

            
            if "status" in topic:
                
                logger.info(f"Status update: {topic} - {payload}")

            elif "anc/result" in topic:
                
                logger.debug(f"ANC result: {topic} - {payload}")

            elif "noise/detected" in topic:
                
                logger.info(f"Noise detected: {topic} - {payload}")
                self._handle_noise_detected(payload)

            elif "noise/stopped" in topic:
                
                logger.info(f"Noise stopped: {topic} - {payload}")
                self._handle_noise_stopped(payload)

            else:
                logger.debug(f"MQTT message: {topic}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON payload from topic: {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)

    def _handle_noise_detected(self, payload: dict):
        """소음 감지 처리 - DB 업데이트"""
        try:
            user_id = payload.get("user_id")
            appliance_name = payload.get("appliance_name")

            if not user_id or not appliance_name:
                logger.warning(f"Invalid noise detected payload: {payload}")
                return

            
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

                    logger.info(f"Appliance {appliance_name} marked as active for user {user_id}")
                else:
                    logger.warning(f"Appliance {appliance_name} not found for user {user_id}")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling noise detected: {e}", exc_info=True)

    def _handle_noise_stopped(self, payload: dict):
        """소음 종료 처리 - DB 업데이트"""
        try:
            user_id = payload.get("user_id")
            appliance_name = payload.get("appliance_name")

            if not user_id or not appliance_name:
                logger.warning(f"Invalid noise stopped payload: {payload}")
                return

            
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

                    logger.info(f"Appliance {appliance_name} marked as inactive for user {user_id}")
                else:
                    logger.warning(f"Appliance {appliance_name} not found for user {user_id}")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling noise stopped: {e}", exc_info=True)

    def on_log(self, client, userdata, level, buf):
        """MQTT 로그"""
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

            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                self.client.username_pw_set(
                    settings.MQTT_USERNAME,
                    settings.MQTT_PASSWORD
                )

            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message
            self.client.on_log = self.on_log

            self.client.will_set(
                "mqtt/status/backend",
                json.dumps({"status": "offline", "timestamp": None}),
                qos=1,
                retain=True
            )

            logger.info(f"Connecting to MQTT Broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}")
            self.client.connect(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                keepalive=60
            )

            self.client.loop_start()

            logger.info("MQTT Service started")

        except Exception as e:
            logger.error(f"Failed to connect to MQTT Broker: {e}", exc_info=True)
            raise

    def disconnect(self):
        """MQTT 브로커 연결 해제"""
        if self.client:
            
            self.client.publish(
                "mqtt/status/backend",
                json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )

            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT Service stopped")

    def publish(self, topic: str, payload: dict, qos: int = 1):
        """MQTT 메시지 발행"""
        if not self.is_connected:
            logger.warning("MQTT not connected, cannot publish")
            return False

        try:
            result = self.client.publish(
                topic,
                json.dumps(payload),
                qos=qos
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: rc={result.rc}")
                return False

        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")
            return False


mqtt_service = MQTTService()
