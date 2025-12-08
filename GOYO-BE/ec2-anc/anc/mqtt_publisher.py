"""
MQTT Publisher for ANC Server
ANC 처리 후 안티노이즈 신호를 Binary Payload로 MQTT 전송
"""
import json
import logging
import struct
import time
from typing import Optional
import paho.mqtt.client as mqtt
import numpy as np
from config import settings

logger = logging.getLogger(__name__)


class MQTTPublisher:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False
        
        self.sequence_numbers = {}  

    def on_connect(self, client, userdata, flags, rc):
        """MQTT 브로커 연결 시 호출"""
        if rc == 0:
            logger.info(" ANC Server connected to MQTT Broker")
            self.is_connected = True

            client.subscribe("mqtt/control/anc/")
            logger.info(" Subscribed to mqtt/control/anc/")
        else:
            logger.error(f" Failed to connect to MQTT Broker, return code {rc}")
            self.is_connected = False

    def on_disconnect(self, client, userdata, rc):
        """MQTT 브로커 연결 해제 시 호출"""
        logger.warning(f" ANC Server disconnected from MQTT Broker (rc: {rc})")
        self.is_connected = False

        if rc != 0:
            logger.info("Attempting to reconnect...")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def on_message(self, client, userdata, msg):
        """제어 명령 수신"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f" Control message received: {topic} - {payload}")
            
        except Exception as e:
            logger.error(f"Error processing control message: {e}")

    def connect(self):
        """MQTT 브로커에 연결"""
        try:
            self.client = mqtt.Client(client_id="goyo-anc-server", clean_session=False)
     
            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                self.client.username_pw_set(
                    settings.MQTT_USERNAME,
                    settings.MQTT_PASSWORD
                )

            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message
            
            self.client.will_set(
                "mqtt/status/anc-server",
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
                logger.info(" MQTT Publisher started")
                
                self.publish_status("online")
            else:
                logger.error(" MQTT connection timeout")

        except Exception as e:
            logger.error(f" Failed to connect to MQTT Broker: {e}", exc_info=True)
            raise

    def disconnect(self):
        """MQTT 브로커 연결 해제"""
        if self.client:
            self.publish_status("offline")
            self.client.loop_stop()
            self.client.disconnect()
            logger.info(" MQTT Publisher stopped")

    def publish_anti_noise(
        self,
        user_id: str,
        anti_noise_data: np.ndarray,
        latency_ms: float = 0.0
    ) -> bool:
        """
        안티노이즈 신호를 Binary Payload로 MQTT 전송

        Args:
            user_id: 사용자 ID
            anti_noise_data: 안티노이즈 신호 (numpy array, float32, -1.0 ~ 1.0)
            latency_ms: 처리 지연시간 (ms)

        Returns:
            성공 여부
        """
        if not self.is_connected:
            logger.warning(" MQTT not connected, cannot publish anti-noise")
            return False

        try:
            anti_noise_int16 = (anti_noise_data * 32767).astype(np.int16)

            if user_id not in self.sequence_numbers:
                self.sequence_numbers[user_id] = 0

            seq = self.sequence_numbers[user_id]

            payload = struct.pack('<I', seq) + anti_noise_int16.tobytes()

            topic = f"mqtt/speaker/output/{user_id}/stream"
            result = self.client.publish(
                topic,
                payload,
                qos=0  
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(
                    f" Published anti-noise to {topic} "
                    f"(seq={seq}, {len(anti_noise_data)} samples, {latency_ms:.1f}ms latency)"
                )

                self.sequence_numbers[user_id] = (seq + 1) % 4294967296
                return True
            else:
                logger.error(f" Failed to publish anti-noise: rc={result.rc}")
                return False

        except Exception as e:
            logger.error(f" Error publishing anti-noise: {e}", exc_info=True)
            return False

    def publish_status(self, status: str, additional_data: dict = None):
        """AI Server 상태 발행"""
        if not self.client:
            return

        payload = {
            "status": status,
            "timestamp": time.time()
        }

        if additional_data:
            payload.update(additional_data)

        try:
            self.client.publish(
                "mqtt/status/anc-server",
                json.dumps(payload),
                qos=1,
                retain=True
            )
            logger.debug(f" Published status: {status}")
        except Exception as e:
            logger.error(f"Error publishing status: {e}")

    def publish_anc_result(
        self,
        user_id: str,
        noise_level_db: float,
        reduction_db: float,
        status: str = "active"
    ):
        """
        ANC 처리 결과를 Backend에 전송 (모니터링용)

        Args:
            user_id: 사용자 ID
            noise_level_db: 노이즈 레벨 (dB)
            reduction_db: 감소량 (dB)
            status: 상태 ("active", "paused", "error" 등)
        """
        if not self.is_connected:
            return

        payload = {
            "user_id": user_id,
            "noise_level_db": round(noise_level_db, 2),
            "reduction_db": round(reduction_db, 2),
            "status": status,
            "timestamp": time.time()
        }

        try:
            topic = f"mqtt/anc/result/{user_id}"
            self.client.publish(
                topic,
                json.dumps(payload),
                qos=0  
            )
            logger.debug(
                f" Published ANC result: "
                f"noise={noise_level_db:.1f}dB, reduction={reduction_db:.1f}dB"
            )
        except Exception as e:
            logger.error(f"Error publishing ANC result: {e}")


mqtt_publisher = MQTTPublisher()
