"""
MQTT Subscriber for ANC Server
"""
import json
import logging
import struct
import time
from typing import Optional, Callable
import paho.mqtt.client as mqtt

from config import settings

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False
        self.on_reference_audio: Optional[Callable] = None
        self.on_error_audio: Optional[Callable] = None
        self.on_control: Optional[Callable] = None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("ANC Server connected to MQTT Broker")
            self.is_connected = True

            client.subscribe("mqtt/audio/reference/+/stream", qos=0)
            client.subscribe("mqtt/audio/reference/+/config", qos=1)
            client.subscribe("mqtt/audio/error/+/stream", qos=0)
            client.subscribe("mqtt/audio/error/+/config", qos=1)
            client.subscribe("mqtt/control/anc/")

            logger.info("Subscribed to MQTT topics:")
            logger.info("   - mqtt/audio/reference/+/stream (binary)")
            logger.info("   - mqtt/audio/reference/+/config (retained)")
            logger.info("   - mqtt/audio/error/+/stream (binary)")
            logger.info("   - mqtt/audio/error/+/config (retained)")
            logger.info("   - mqtt/control/anc/")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")
            self.is_connected = False

    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"ANC Server disconnected from MQTT Broker (rc: {rc})")
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

            if "/config" in topic:
                config = json.loads(msg.payload.decode('utf-8'))
                logger.debug(f"Received config: {topic} - {config}")
                return

            if "audio/reference" in topic and "/stream" in topic:
                if len(msg.payload) < 4:
                    logger.warning(f"Invalid payload size: {len(msg.payload)}")
                    return

                sequence = struct.unpack('<I', msg.payload[:4])[0]
                audio_bytes = msg.payload[4:]

                user_id = topic.split('/')[3]

                if self.on_reference_audio:
                    payload = {
                        "user_id": user_id,
                        "sequence": sequence,
                        "audio_data": audio_bytes,
                        "timestamp": time.time()
                    }
                    self.on_reference_audio(payload)
                else:
                    logger.warning("No handler for reference audio")

            
            elif "audio/error" in topic and "/stream" in topic:
                if len(msg.payload) < 4:
                    logger.warning(f"Invalid payload size: {len(msg.payload)}")
                    return

                sequence = struct.unpack('<I', msg.payload[:4])[0]
                audio_bytes = msg.payload[4:]

                user_id = topic.split('/')[3]

                if self.on_error_audio:
                    payload = {
                        "user_id": user_id,
                        "sequence": sequence,
                        "audio_data": audio_bytes,
                        "timestamp": time.time()
                    }
                    self.on_error_audio(payload)
                else:
                    logger.warning("No handler for error audio")

            
            elif "control/anc" in topic:
                control_payload = json.loads(msg.payload.decode('utf-8'))
                if self.on_control:
                    self.on_control(control_payload)
                else:
                    logger.info(f"Control message: {control_payload}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from topic: {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)

    def connect(self):
        """MQTT 브로커에 연결"""
        try:
            self.client = mqtt.Client(
                client_id="goyo-anc-server-subscriber",
                clean_session=False
            )

            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                self.client.username_pw_set(
                    settings.MQTT_USERNAME,
                    settings.MQTT_PASSWORD
                )

            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message

            self.client.will_set(
                "mqtt/status/anc-server/subscriber",
                json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )

            logger.info(
                f"Connecting to MQTT Broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}"
            )
            self.client.connect(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                keepalive=60
            )

            self.client.loop_start()

            wait_count = 0
            while not self.is_connected and wait_count < 50:
                time.sleep(0.1)
                wait_count += 1

            if self.is_connected:
                logger.info("MQTT Subscriber started")
                self.publish_status("online")
            else:
                logger.error("MQTT connection timeout")

        except Exception as e:
            logger.error(f"Failed to connect to MQTT Broker: {e}", exc_info=True)
            raise

    def disconnect(self):
        """MQTT 브로커 연결 해제"""
        if self.client:
            self.publish_status("offline")
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT Subscriber stopped")

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
                logger.debug(f"Published status: {status}")
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


mqtt_subscriber = MQTTSubscriber()
