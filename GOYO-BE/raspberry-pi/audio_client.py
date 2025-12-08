"""
GOYO Raspberry Pi Audio Client
"""
import alsaaudio
import paho.mqtt.client as mqtt
import json
import struct
import time
import logging
import signal
import sys
import os
import numpy as np
import threading
from typing import Optional
from dataclasses import dataclass
from queue import Queue

try:
    from rpi_inference import YAMNetClassifier
    YAMNET_AVAILABLE = True
except ImportError:
    logging.warning("rpi_inference.py not found. VAD filtering will be disabled.")
    YAMNET_AVAILABLE = False

@dataclass
class Config:
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = "raspberry_pi"
    MQTT_PASSWORD: str = ""

    USER_ID: str = "1"
    DEVICE_ID: str = "goyo-rpi-default"

    SAMPLE_RATE: int = 48000
    CHANNELS: int = 1
    CHUNK_SIZE: int = 48000

    REFERENCE_MIC_DEVICE: str = "hw:3,0"
    ERROR_MIC_DEVICE: str = "hw:2,0"
    SPEAKER_DEVICE: str = "hw:4,0"

    LOG_LEVEL: str = "DEBUG"

    VAD_ENABLED: bool = True
    VAD_THRESHOLD_DB: float = 60.0
    CHUNK_DURATION: float = 1.0
    NUM_CHUNKS: int = 5
    CHUNK_OVERLAP: float = 0.5
    CONSISTENCY_THRESHOLD: int = 4

    CLASSIFIER_MODEL_PATH: str = "models/classifier.tflite"

    APPLIANCE_TYPE: str = None
    APPLIANCE_ID: int = None


config = Config()

CONFIG_FILE = os.path.expanduser("~/goyo/goyo_config.json")
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            mqtt_config = json.load(f)
            config.MQTT_BROKER_HOST = mqtt_config.get('mqtt_broker_host', config.MQTT_BROKER_HOST)
            config.MQTT_BROKER_PORT = mqtt_config.get('mqtt_broker_port', config.MQTT_BROKER_PORT)
            config.MQTT_USERNAME = mqtt_config.get('mqtt_username', config.MQTT_USERNAME)
            config.MQTT_PASSWORD = mqtt_config.get('mqtt_password', config.MQTT_PASSWORD)
            config.USER_ID = mqtt_config.get('user_id', config.USER_ID)
            config.APPLIANCE_TYPE = mqtt_config.get("appliance_type")
            config.APPLIANCE_ID = mqtt_config.get("appliance_id")
            config.DEVICE_ID = mqtt_config.get('device_id', config.DEVICE_ID)
            logging.info(f"Loaded MQTT config from {CONFIG_FILE}")
    except Exception as e:
        logging.warning(f"Failed to load config file: {e}")

logging.basicConfig(
    force=True,
    level=getattr(logging, config.LOG_LEVEL),
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class VADFilter:
    def __init__(self, mqtt_client):
        self.mqtt_client = mqtt_client
        self.state = "MONITORING"
        self.audio_buffer = []
        self.inference_queue = []
        self.classifier = None

        if config.VAD_ENABLED:
            if YAMNET_AVAILABLE:
                try:
                    logger.info(f"Loading YAMNet unified model...")
                    self.classifier = YAMNetClassifier(
                        classifier_path=config.CLASSIFIER_MODEL_PATH
                    )
                    logger.info("YAMNet 통합 모델 로드 완료")
                except Exception as e:
                    logger.error(f"분류기 로드 실패: {e}")
                    logger.warning("→ VAD 비활성화")
                    config.VAD_ENABLED = False
                    self.classifier = None
            else:
                logger.warning("rpi_inference 모듈 없음 - VAD 비활성화")
                config.VAD_ENABLED = False
                self.classifier = None

        logger.info("VAD Filter initialized")

    def calculate_rms_db(self, audio_chunk: bytes) -> float:
        try:
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            if rms > 0:
                db = 20 * np.log10(rms / 32768.0) + 90
            else:
                db = 0
            return db
        except Exception as e:
            logger.error(f"Error calculating RMS dB: {e}")
            return 0.0

    def process_chunk(self, audio_chunk: bytes) -> Optional[str]:
        if not config.VAD_ENABLED:
            return "APPLIANCE_DETECTED"

        db_level = self.calculate_rms_db(audio_chunk)

        if self.state == "MONITORING":
            if db_level >= config.VAD_THRESHOLD_DB:
                logger.info(f"VAD Triggered: {db_level:.1f} dB")
                self.state = "BUFFERING"
                self.inference_queue = []
                self.audio_buffer = audio_chunk
                logger.info("→ Buffering mode started")
                return "BUFFERING"
            return None

        elif self.state == "BUFFERING":
            if db_level < config.VAD_THRESHOLD_DB:
                logger.info(f"Noise stopped: {db_level:.1f} dB")
                self.state = "MONITORING"
                self.inference_queue = []
                self.audio_buffer = []
                return "SOUND_STOPPED"

            
            if self.audio_buffer:
                half_chunk = len(audio_chunk) // 2
                prev_half = self.audio_buffer[half_chunk:]
                curr_half = audio_chunk[:half_chunk]
                overlapped_chunk = prev_half + curr_half
                self.inference_queue.append(overlapped_chunk)
            else:
                self.inference_queue.append(audio_chunk)

            self.audio_buffer = audio_chunk

            
            if len(self.inference_queue) == config.NUM_CHUNKS:
                logger.info(f"Buffer full - Running DL inference...")
                result = self.classify_noise()
                self.inference_queue = []
                self.audio_buffer = []
                self.state = "MONITORING"
                return result

            
            return "BUFFERING"

        return None

    def classify_noise(self) -> Optional[str]:
        """YAMNet TFLite로 소음 분류"""
        try:
            if not config.VAD_ENABLED or not self.classifier:
                return "APPLIANCE_DETECTED"

            logger.info("YAMNet 분류 시작...")
            result = self.classifier.classify_buffer(
                self.inference_queue,
                consistency_threshold=config.CONSISTENCY_THRESHOLD,
                source_rate=48000,
                target_class=config.APPLIANCE_ID
            )

            if result == "APPLIANCE_DETECTED":
                logger.info("가전 소음 확인 - ANC 시작")
                self.send_anc_start_command()
                return "APPLIANCE_DETECTED"
            else:
                
                logger.info("대상 가전 아님 - ANC 중지")
                return "SOUND_STOPPED"

        except Exception as e:
            logger.error(f"분류 오류: {e}", exc_info=True)
            return None

    def send_anc_start_command(self):
        """MQTT로 ANC 시작 명령 전송"""
        payload = {
            "command": "start",
            "user_id": config.USER_ID,
            "device_type": "appliance_noise",
            "timestamp": time.time()
        }

        topic = f"mqtt/control/anc/{config.USER_ID}"

        try:
            self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            logger.info(f"Published ANC start command")
        except Exception as e:
            logger.error(f"Error publishing ANC start: {e}")


class AudioClient:
    def __init__(self):
        self.mqtt_client: Optional[mqtt.Client] = None
        self.is_running = False
        self.mqtt_connected = False

        
        self.reference_mic: Optional[alsaaudio.PCM] = None
        self.error_mic: Optional[alsaaudio.PCM] = None
        self.speaker: Optional[alsaaudio.PCM] = None

        
        self.reference_thread: Optional[threading.Thread] = None
        self.error_thread: Optional[threading.Thread] = None
        self.speaker_thread: Optional[threading.Thread] = None

        
        self.speaker_queue = Queue(maxsize=10)

        
        self.vad_filter: Optional[VADFilter] = None

        
        self.anc_active = False

        
        self.reference_seq = 0
        self.error_seq = 0

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT 연결 성공 시 호출"""
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            self.mqtt_connected = True

            
            if self.vad_filter is None:
                self.vad_filter = VADFilter(self.mqtt_client)

            
            self.publish_status("online")

            
            self.publish_audio_config()

            
            client.subscribe(f"mqtt/control/raspberry/{config.USER_ID}", qos=1)
            client.subscribe(f"mqtt/speaker/output/{config.USER_ID}/stream", qos=0)
            logger.info(f"Subscribed to control and speaker topics")
        else:
            logger.error(f"Failed to connect to MQTT Broker, rc={rc}")
            self.mqtt_connected = False

    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT 연결 해제"""
        logger.warning(f"⚠️ Disconnected from MQTT Broker (rc: {rc})")
        self.mqtt_connected = False

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT 메시지 수신"""
        try:
            topic = msg.topic

            
            if "speaker/output" in topic and "/stream" in topic:
                self.handle_anti_noise(msg.payload)
                return

            
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"Control command: {payload}")

            command = payload.get("command")
            if command == "stop":
                self.stop()

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def handle_anti_noise(self, payload: bytes):
        """안티노이즈 신호 처리"""
        try:
            if len(payload) < 4:
                return

            sequence = struct.unpack('<I', payload[:4])[0]
            audio_bytes = payload[4:]

            
            if self.speaker_queue.full():
                try:
                    self.speaker_queue.get_nowait()
                except:
                    pass

            self.speaker_queue.put(audio_bytes)
            

        except Exception as e:
            logger.error(f"Error handling anti-noise: {e}")

    def connect_mqtt(self):
        """MQTT 브로커 연결"""
        try:
            self.mqtt_client = mqtt.Client(
                client_id=config.DEVICE_ID,
                clean_session=True
            )

            self.mqtt_client.username_pw_set(
                config.MQTT_USERNAME,
                config.MQTT_PASSWORD
            )

            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_mqtt_message

            
            self.mqtt_client.will_set(
                f"mqtt/status/raspberry/{config.USER_ID}",
                json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )

            logger.info(f"Connecting to MQTT: {config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT}")
            self.mqtt_client.connect(
                config.MQTT_BROKER_HOST,
                config.MQTT_BROKER_PORT,
                keepalive=60
            )

            self.mqtt_client.loop_start()

            
            wait_count = 0
            while not self.mqtt_connected and wait_count < 50:
                time.sleep(0.1)
                wait_count += 1

            if not self.mqtt_connected:
                logger.error("MQTT connection timeout")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}", exc_info=True)
            return False

    def open_audio_devices(self):
        """alsaaudio 디바이스 열기"""
        try:
            
            self.reference_mic = alsaaudio.PCM(
                alsaaudio.PCM_CAPTURE,
                device=config.REFERENCE_MIC_DEVICE,
                channels=config.CHANNELS,
                rate=config.SAMPLE_RATE,
                format=alsaaudio.PCM_FORMAT_S16_LE,
                periodsize=config.CHUNK_SIZE
            )
            logger.info(f"Reference mic opened: {config.REFERENCE_MIC_DEVICE}")

            
            if config.ERROR_MIC_DEVICE:
                self.error_mic = alsaaudio.PCM(
                    alsaaudio.PCM_CAPTURE,
                    device=config.ERROR_MIC_DEVICE,
                    channels=config.CHANNELS,
                    rate=config.SAMPLE_RATE,
                    format=alsaaudio.PCM_FORMAT_S16_LE,
                    periodsize=config.CHUNK_SIZE
                )
                logger.info(f"Error mic opened: {config.ERROR_MIC_DEVICE}")

            
            try:
                self.speaker = alsaaudio.PCM(
                    alsaaudio.PCM_PLAYBACK,
                    device=config.SPEAKER_DEVICE,
                    channels=config.CHANNELS,
                    rate=config.SAMPLE_RATE,
                    format=alsaaudio.PCM_FORMAT_S16_LE,
                    periodsize=config.CHUNK_SIZE
                )
                logger.info(f"Speaker opened: {config.SPEAKER_DEVICE}")
            except Exception as speaker_error:
                logger.warning(f"⚠️ Speaker not available: {speaker_error}")
                self.speaker = None

            return True

        except Exception as e:
            logger.error(f"Failed to open audio devices: {e}", exc_info=True)
            return False

    def reference_mic_thread_func(self):
        """Reference 마이크 스레드"""
        logger.info("Reference mic thread started")

        while self.is_running and self.reference_mic:
            try:
                
                length, audio_data = self.reference_mic.read()

                if length > 0 and self.mqtt_connected:
                    
                    if self.vad_filter and config.VAD_ENABLED:
                        result = self.vad_filter.process_chunk(audio_data)

                        if result == "APPLIANCE_DETECTED":
                            logger.info("Appliance noise detected - Activating ANC")
                            self.anc_active = True
                        elif result == "SOUND_STOPPED":
                            
                            logger.info("ANC deactivated - Sound stopped")
                            self.anc_active = False
                        

                    
                    if self.anc_active or not config.VAD_ENABLED:
                        payload = struct.pack('<I', self.reference_seq) + audio_data

                        self.mqtt_client.publish(
                            f"mqtt/audio/reference/{config.USER_ID}/stream",
                            payload,
                            qos=0
                        )

                        self.reference_seq = (self.reference_seq + 1) % 4294967296

            except Exception as e:
                logger.error(f"Error in reference mic thread: {e}")
                time.sleep(0.1)

        logger.info("Reference mic thread stopped")

    def error_mic_thread_func(self):
        """Error 마이크 스레드"""
        logger.info("Error mic thread started")

        while self.is_running and self.error_mic:
            try:
                
                length, audio_data = self.error_mic.read()

                if length > 0 and self.mqtt_connected:
                    
                    if self.anc_active or not config.VAD_ENABLED:
                        payload = struct.pack('<I', self.error_seq) + audio_data

                        self.mqtt_client.publish(
                            f"mqtt/audio/error/{config.USER_ID}/stream",
                            payload,
                            qos=0
                        )

                        self.error_seq = (self.error_seq + 1) % 4294967296

            except Exception as e:
                logger.error(f"Error in error mic thread: {e}")
                time.sleep(0.1)

        logger.info("Error mic thread stopped")

    def speaker_thread_func(self):
        """스피커 출력 스레드"""
        logger.info("Speaker thread started")

        while self.is_running and self.speaker:
            try:
                if not self.speaker_queue.empty():
                    audio_bytes = self.speaker_queue.get()
                    self.speaker.write(audio_bytes)
                else:
                    time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in speaker thread: {e}")
                time.sleep(0.1)

        logger.info("Speaker thread stopped")

    def publish_audio_config(self):
        """오디오 설정 발행"""
        if self.mqtt_client:
            config_payload = {
                "sr": config.SAMPLE_RATE,
                "ch": config.CHANNELS,
                "dt": "i16",
                "cs": config.CHUNK_SIZE
            }
            try:
                self.mqtt_client.publish(
                    f"mqtt/audio/reference/{config.USER_ID}/config",
                    json.dumps(config_payload),
                    qos=1,
                    retain=True
                )
                self.mqtt_client.publish(
                    f"mqtt/audio/error/{config.USER_ID}/config",
                    json.dumps(config_payload),
                    qos=1,
                    retain=True
                )
                logger.info(f"Published audio config: {config_payload}")
            except Exception as e:
                logger.error(f"Error publishing audio config: {e}")

    def publish_status(self, status: str):
        """상태 발행"""
        if self.mqtt_client:
            payload = {
                "status": status,
                "user_id": config.USER_ID,
                "timestamp": time.time()
            }
            try:
                self.mqtt_client.publish(
                    f"mqtt/status/raspberry/{config.USER_ID}",
                    json.dumps(payload),
                    qos=1,
                    retain=True
                )
                logger.debug(f"Published status: {status}")
            except Exception as e:
                logger.error(f"Error publishing status: {e}")

    def start(self):
        
        """오디오 캡처 및 전송 시작"""
        print("DEBUG: About to log starting message", flush=True)
        logger.info("Starting GOYO Audio Client (alsaaudio)...")

        
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT, exiting")
            return False

        
        if not self.open_audio_devices():
            logger.error("Failed to open audio devices, exiting")
            return False

        
        self.is_running = True

        self.reference_thread = threading.Thread(
            target=self.reference_mic_thread_func,
            daemon=True
        )
        self.reference_thread.start()

        if self.error_mic:
            self.error_thread = threading.Thread(
                target=self.error_mic_thread_func,
                daemon=True
            )
            self.error_thread.start()

        if self.speaker:
            self.speaker_thread = threading.Thread(
                target=self.speaker_thread_func,
                daemon=True
            )
            self.speaker_thread.start()

        logger.info("Audio capture started")
        logger.info("Press Ctrl+C to stop")

        
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")

        return True

    def stop(self):
        """오디오 캡처 중지"""
        logger.info("Stopping audio client...")
        self.is_running = False

        
        if self.reference_thread:
            self.reference_thread.join(timeout=2)
        if self.error_thread:
            self.error_thread.join(timeout=2)
        if self.speaker_thread:
            self.speaker_thread.join(timeout=2)

        
        if self.reference_mic:
            self.reference_mic.close()
        if self.error_mic:
            self.error_mic.close()
        if self.speaker:
            self.speaker.close()

        
        while not self.speaker_queue.empty():
            try:
                self.speaker_queue.get_nowait()
            except:
                break

        
        if self.mqtt_client:
            self.publish_status("offline")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

        logger.info("Audio client stopped")

    def cleanup(self, signum, frame):
        """Signal handler"""
        logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)


def main():
    """메인 함수"""
    client = AudioClient()

    
    signal.signal(signal.SIGINT, client.cleanup)
    signal.signal(signal.SIGTERM, client.cleanup)

    
    client.start()


if __name__ == "__main__":
    main()
