#!/usr/bin/env python3
"""
GOYO Raspberry Pi Audio Client
라즈베리파이에서 USB 마이크로 오디오 캡처 후 MQTT로 전송
+ VAD 필터링 및 가전 소음 분류 (Edge AI)
+ 서버에서 받은 안티노이즈 신호를 스피커로 출력
"""
import pyaudio
import paho.mqtt.client as mqtt
import json
import base64
import time
import logging
import signal
import sys
import numpy as np
from typing import Optional
from dataclasses import dataclass
from queue import Queue

# TFLite Runtime (설치: pip3 install tflite-runtime)
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
except ImportError:
    logging.warning("⚠️ tflite-runtime not installed. VAD filtering will use mock mode.")
    TFLITE_AVAILABLE = False

# 환경설정 (또는 .env 파일에서 로드)
@dataclass
class Config:
    # MQTT
    MQTT_BROKER_HOST: str = "3.x.x.x"  # ⚠️ EC2 #1의 Public IP로 변경
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = "raspberry_pi"
    MQTT_PASSWORD: str = "raspi_mqtt_pass_2025"

    # 사용자 정보
    USER_ID: str = "1"  # ⚠️ Backend에서 생성한 사용자 ID

    # 오디오 설정
    SAMPLE_RATE: int = 16000  # AI 요구사항: 16kHz
    CHANNELS: int = 1  # Mono
    CHUNK_SIZE: int = 16000  # 1초 = 16000 샘플 @ 16kHz
    FORMAT: int = pyaudio.paInt16

    # 마이크 디바이스 인덱스 (arecord -l로 확인)
    REFERENCE_MIC_INDEX: Optional[int] = None  # None이면 기본 장치
    ERROR_MIC_INDEX: Optional[int] = None

    # 스피커 디바이스 인덱스
    SPEAKER_INDEX: Optional[int] = None  # None이면 기본 장치

    # 로깅
    LOG_LEVEL: str = "INFO"

    # VAD (Voice Activity Detection) 설정
    VAD_ENABLED: bool = True            # VAD 필터링 활성화
    VAD_THRESHOLD_DB: float = 65.0      # RMS dB 임계치
    CHUNK_DURATION: float = 1.0         # 1.0초 청크 (AI 요구사항)
    NUM_CHUNKS: int = 5                 # 5개 청크 수집 (AI 요구사항: 5x16000)
    CONSISTENCY_THRESHOLD: int = 5      # 5개 중 5개 일관성

    # DL 모델
    MODEL_PATH: str = "models/vacuum_classifier.tflite"
    USE_MOCK_MODEL: bool = True         # Mock 모델 사용 (개발/테스트용)


config = Config()

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VADFilter:
    """
    Voice Activity Detection + Buffering + DL Classification

    가전 소음을 감지하여 ANC 활성화 트리거
    - Phase 1: 대기 모드 (0.5초마다 dB만 체크)
    - Phase 2: 버퍼링 모드 (3초간 오디오 수집)
    - Phase 3: DL 추론 (가전 소음 판단)
    """

    def __init__(self, mqtt_client):
        self.mqtt_client = mqtt_client
        self.state = "MONITORING"  # MONITORING or BUFFERING
        self.audio_buffer = []
        self.inference_queue = []

        # DL 모델 로드
        self.interpreter = None
        self.input_details = None
        self.output_details = None

        if config.VAD_ENABLED and not config.USE_MOCK_MODEL:
            if TFLITE_AVAILABLE:
                try:
                    logger.info(f"Loading DL model from {config.MODEL_PATH}")
                    self.interpreter = tflite.Interpreter(model_path=config.MODEL_PATH)
                    self.interpreter.allocate_tensors()
                    self.input_details = self.interpreter.get_input_details()
                    self.output_details = self.interpreter.get_output_details()
                    logger.info("✅ TFLite model loaded successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to load model: {e}")
                    logger.info("→ Falling back to mock mode")
                    config.USE_MOCK_MODEL = True
            else:
                logger.warning("TFLite not available - using mock mode")
                config.USE_MOCK_MODEL = True

        if config.USE_MOCK_MODEL:
            logger.info("🧪 VAD Filter running in MOCK MODE")

        logger.info("✅ VAD Filter initialized")

    def calculate_rms_db(self, audio_chunk: bytes) -> float:
        """RMS dB 계산"""
        try:
            # bytes → numpy array (int16)
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)

            # RMS 계산
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))

            # dB 변환 (reference: 32768 = max int16)
            if rms > 0:
                db = 20 * np.log10(rms / 32768.0) + 90  # normalize to ~0-90 dB
            else:
                db = 0

            return db
        except Exception as e:
            logger.error(f"Error calculating RMS dB: {e}")
            return 0.0

    def process_chunk(self, audio_chunk: bytes) -> Optional[str]:
        """
        1초 오디오 청크 처리 (AI 요구사항: 16000 샘플)

        Returns:
            - None: 계속 대기/버퍼링
            - "APPLIANCE_DETECTED": 가전 소음 감지, ANC 시작
        """
        if not config.VAD_ENABLED:
            return "APPLIANCE_DETECTED"  # VAD 비활성화 시 항상 통과

        db_level = self.calculate_rms_db(audio_chunk)

        # ─────────────────────────────────────
        # STATE: MONITORING
        # ─────────────────────────────────────
        if self.state == "MONITORING":
            if db_level >= config.VAD_THRESHOLD_DB:
                logger.info(f"🔊 VAD Triggered: {db_level:.1f} dB (>= {config.VAD_THRESHOLD_DB})")
                self.state = "BUFFERING"
                self.inference_queue = []
                logger.info("→ Buffering mode started")

        # ─────────────────────────────────────
        # STATE: BUFFERING
        # ─────────────────────────────────────
        elif self.state == "BUFFERING":
            # Kill Switch: dB가 임계치 이하로 떨어지면 즉시 중단
            if db_level < config.VAD_THRESHOLD_DB:
                logger.info(f"🔇 Noise stopped: {db_level:.1f} dB (< {config.VAD_THRESHOLD_DB})")
                logger.info("→ Back to monitoring mode")
                self.state = "MONITORING"
                self.inference_queue = []
                return None

            # 1초 청크를 바로 inference_queue에 추가
            self.inference_queue.append(audio_chunk)

            logger.debug(f"📦 Chunk added: {len(self.inference_queue)}/{config.NUM_CHUNKS}")

            # 5개 청크 모두 수집 완료?
            if len(self.inference_queue) == config.NUM_CHUNKS:
                logger.info(f"✅ Buffer full ({config.NUM_CHUNKS} chunks) - Running DL inference...")
                result = self.classify_noise()

                # 초기화
                self.inference_queue = []
                self.state = "MONITORING"

                return result

        return None

    def classify_noise(self) -> Optional[str]:
        """DL 모델로 소음 분류 - 입력 형태: (5, 16000) Float32"""
        try:
            if config.USE_MOCK_MODEL:
                # Mock 모드: 항상 가전 소음으로 판단 (개발용)
                logger.info("🧪 MOCK: Simulating appliance noise detection")
                appliance_count = config.NUM_CHUNKS  # 5/5
            else:
                # 실제 TFLite 모델 추론
                # 5개 청크를 (5, 16000) Float32 numpy array로 변환
                input_data = []
                for chunk in self.inference_queue:
                    audio_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                    # 정규화 [-1.0, 1.0] (AI 요구사항)
                    audio_np = audio_np / 32768.0
                    input_data.append(audio_np)

                # (5, 16000) 형태로 변환
                input_data = np.array(input_data, dtype=np.float32)
                logger.debug(f"📐 Input shape: {input_data.shape}")  # Should be (5, 16000)

                # 모델 입력 형태에 맞게 reshape (필요시)
                # AI 팀 모델이 (5, 16000) 그대로 받는다면 그대로 사용
                # 배치 차원이 필요하면: input_data = np.expand_dims(input_data, axis=0)

                # TFLite 추론
                self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
                self.interpreter.invoke()
                output = self.interpreter.get_tensor(self.output_details[0]['index'])

                # 출력 해석
                # AI 팀에서 제공한 출력 형태에 맞게 조정 필요
                # 가정: output shape = (5, 2) → [외부소음 확률, 가전소음 확률] per chunk
                predictions = output  # (5, 2)

                # 5/5 일관성 체크
                appliance_count = np.sum(predictions[:, 1] > 0.5)

            logger.info(f"📊 DL Results: {appliance_count}/{config.NUM_CHUNKS} chunks classified as appliance noise")

            if appliance_count >= config.CONSISTENCY_THRESHOLD:
                logger.info("✅ Appliance noise confirmed!")
                self.send_anc_start_command()
                return "APPLIANCE_DETECTED"
            else:
                logger.info("❌ External noise - ignoring")
                return None

        except Exception as e:
            logger.error(f"❌ DL inference error: {e}", exc_info=True)
            return None

    def send_anc_start_command(self):
        """MQTT로 ANC 시작 명령 전송"""
        payload = {
            "command": "start",
            "user_id": config.USER_ID,
            "device_type": "vacuum_cleaner",
            "timestamp": time.time()
        }

        topic = f"mqtt/control/ai/{config.USER_ID}"

        try:
            self.mqtt_client.publish(
                topic,
                json.dumps(payload),
                qos=1
            )
            logger.info(f"📤 Published ANC start command to {topic}")
        except Exception as e:
            logger.error(f"Error publishing ANC start: {e}")


class AudioClient:
    def __init__(self):
        self.mqtt_client: Optional[mqtt.Client] = None
        self.pyaudio = pyaudio.PyAudio()
        self.reference_stream: Optional[pyaudio.Stream] = None
        self.error_stream: Optional[pyaudio.Stream] = None
        self.speaker_stream: Optional[pyaudio.Stream] = None
        self.is_running = False
        self.mqtt_connected = False

        # 스피커 출력용 오디오 큐
        self.speaker_queue = Queue(maxsize=10)

        # VAD Filter (MQTT 연결 후 초기화)
        self.vad_filter: Optional[VADFilter] = None

        # ANC 활성화 상태
        self.anc_active = False

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT 연결 성공 시 호출"""
        if rc == 0:
            logger.info("✅ Connected to MQTT Broker")
            self.mqtt_connected = True

            # VAD Filter 초기화
            self.vad_filter = VADFilter(self.mqtt_client)

            # 상태 발행
            self.publish_status("online")

            # 제어 명령 구독 (필요 시)
            client.subscribe(f"mqtt/control/raspberry/{config.USER_ID}", qos=1)
            logger.info(f"📡 Subscribed to mqtt/control/raspberry/{config.USER_ID}")

            # 스피커 출력 신호 구독
            client.subscribe(f"mqtt/speaker/output/{config.USER_ID}", qos=1)
            logger.info(f"📡 Subscribed to mqtt/speaker/output/{config.USER_ID}")
        else:
            logger.error(f"❌ Failed to connect to MQTT Broker, return code {rc}")
            self.mqtt_connected = False

    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT 연결 해제 시 호출"""
        logger.warning(f"⚠️ Disconnected from MQTT Broker (rc: {rc})")
        self.mqtt_connected = False

        if rc != 0:
            logger.info("Attempting to reconnect...")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT 메시지 수신 - 제어 명령 또는 안티노이즈 신호"""
        try:
            topic = msg.topic

            # 스피커 출력 신호 수신
            if "speaker/output" in topic:
                payload = json.loads(msg.payload.decode('utf-8'))
                self.handle_anti_noise(payload)
                return

            # 제어 명령 수신
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"🎛️ Control command received: {payload}")

            command = payload.get("command")
            if command == "stop":
                logger.info("Stop command received")
                self.stop()
            elif command == "adjust":
                logger.info(f"Adjust command: {payload}")
                # TODO: 필요 시 설정 조정

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def handle_anti_noise(self, payload: dict):
        """안티노이즈 신호 처리 및 스피커 큐에 추가"""
        try:
            # Base64 디코딩
            anti_noise_b64 = payload.get("anti_noise_data")
            audio_bytes = base64.b64decode(anti_noise_b64)

            # 큐가 가득 차면 이전 데이터 버림 (최신 데이터 우선)
            if self.speaker_queue.full():
                try:
                    self.speaker_queue.get_nowait()
                except:
                    pass

            # 큐에 오디오 데이터 추가
            self.speaker_queue.put(audio_bytes)

            logger.debug(f"🔊 Anti-noise received: {len(audio_bytes)} bytes")

        except Exception as e:
            logger.error(f"Error handling anti-noise: {e}")

    def connect_mqtt(self):
        """MQTT 브로커 연결"""
        try:
            self.mqtt_client = mqtt.Client(
                client_id=f"raspberry-pi-{config.USER_ID}",
                clean_session=False
            )

            # 인증
            self.mqtt_client.username_pw_set(
                config.MQTT_USERNAME,
                config.MQTT_PASSWORD
            )

            # 콜백 등록
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_mqtt_message

            # Will 메시지
            self.mqtt_client.will_set(
                f"mqtt/status/raspberry/{config.USER_ID}",
                json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )

            # 연결
            logger.info(
                f"Connecting to MQTT Broker at {config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT}"
            )
            self.mqtt_client.connect(
                config.MQTT_BROKER_HOST,
                config.MQTT_BROKER_PORT,
                keepalive=60
            )

            # 백그라운드 루프 시작
            self.mqtt_client.loop_start()

            # 연결 대기
            wait_count = 0
            while not self.mqtt_connected and wait_count < 50:
                time.sleep(0.1)
                wait_count += 1

            if not self.mqtt_connected:
                logger.error("❌ MQTT connection timeout")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to MQTT Broker: {e}", exc_info=True)
            return False

    def list_audio_devices(self):
        """사용 가능한 오디오 디바이스 목록 출력"""
        logger.info("Available audio devices:")
        for i in range(self.pyaudio.get_device_count()):
            info = self.pyaudio.get_device_info_by_index(i)
            logger.info(
                f"  {i}: {info['name']} "
                f"(Inputs: {info['maxInputChannels']}, "
                f"Outputs: {info['maxOutputChannels']})"
            )

    def open_streams(self):
        """오디오 스트림 열기"""
        try:
            # Reference 마이크
            self.reference_stream = self.pyaudio.open(
                format=config.FORMAT,
                channels=config.CHANNELS,
                rate=config.SAMPLE_RATE,
                input=True,
                input_device_index=config.REFERENCE_MIC_INDEX,
                frames_per_buffer=config.CHUNK_SIZE,
                stream_callback=self.reference_callback
            )
            logger.info(f"✅ Reference microphone opened (device: {config.REFERENCE_MIC_INDEX})")

            # Error 마이크 (선택사항)
            if config.ERROR_MIC_INDEX is not None:
                self.error_stream = self.pyaudio.open(
                    format=config.FORMAT,
                    channels=config.CHANNELS,
                    rate=config.SAMPLE_RATE,
                    input=True,
                    input_device_index=config.ERROR_MIC_INDEX,
                    frames_per_buffer=config.CHUNK_SIZE,
                    stream_callback=self.error_callback
                )
                logger.info(f"✅ Error microphone opened (device: {config.ERROR_MIC_INDEX})")
            else:
                logger.info("⚠️ Error microphone not configured")

            # 스피커 출력 스트림
            self.speaker_stream = self.pyaudio.open(
                format=config.FORMAT,
                channels=config.CHANNELS,
                rate=config.SAMPLE_RATE,
                output=True,
                output_device_index=config.SPEAKER_INDEX,
                frames_per_buffer=config.CHUNK_SIZE,
                stream_callback=self.speaker_callback
            )
            logger.info(f"✅ Speaker opened (device: {config.SPEAKER_INDEX})")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to open audio streams: {e}", exc_info=True)
            return False

    def reference_callback(self, in_data, frame_count, time_info, status):
        """Reference 마이크 콜백 - VAD 필터링 후 MQTT로 전송"""
        if self.mqtt_connected and self.is_running:
            try:
                # VAD 필터 처리
                if self.vad_filter and config.VAD_ENABLED:
                    result = self.vad_filter.process_chunk(in_data)

                    if result == "APPLIANCE_DETECTED":
                        logger.info("🎯 Appliance noise detected - Activating ANC mode")
                        self.anc_active = True

                # ANC 활성화 상태일 때만 오디오 데이터 전송
                if self.anc_active or not config.VAD_ENABLED:
                    payload = {
                        "user_id": config.USER_ID,
                        "audio_data": base64.b64encode(in_data).decode('utf-8'),
                        "timestamp": time.time(),
                        "sample_rate": config.SAMPLE_RATE,
                        "channels": config.CHANNELS,
                        "frame_count": frame_count
                    }

                    self.mqtt_client.publish(
                        f"mqtt/audio/reference/{config.USER_ID}",
                        json.dumps(payload),
                        qos=1
                    )

            except Exception as e:
                logger.error(f"Error publishing reference audio: {e}")

        return (None, pyaudio.paContinue)

    def error_callback(self, in_data, frame_count, time_info, status):
        """Error 마이크 콜백 - ANC 활성화 시에만 전송"""
        if self.mqtt_connected and self.is_running:
            try:
                # ANC 활성화 상태일 때만 오디오 데이터 전송
                if self.anc_active or not config.VAD_ENABLED:
                    payload = {
                        "user_id": config.USER_ID,
                        "audio_data": base64.b64encode(in_data).decode('utf-8'),
                        "timestamp": time.time(),
                        "sample_rate": config.SAMPLE_RATE,
                        "channels": config.CHANNELS,
                        "frame_count": frame_count
                    }

                    self.mqtt_client.publish(
                        f"mqtt/audio/error/{config.USER_ID}",
                        json.dumps(payload),
                        qos=1
                    )

            except Exception as e:
                logger.error(f"Error publishing error audio: {e}")

        return (None, pyaudio.paContinue)

    def speaker_callback(self, in_data, frame_count, time_info, status):
        """스피커 콜백 - 큐에서 안티노이즈 신호 가져와서 재생"""
        try:
            if not self.speaker_queue.empty():
                # 큐에서 오디오 데이터 가져오기
                audio_bytes = self.speaker_queue.get_nowait()

                # 데이터 길이 확인 및 조정
                required_bytes = frame_count * config.CHANNELS * 2  # int16 = 2 bytes

                if len(audio_bytes) < required_bytes:
                    # 데이터가 부족하면 0으로 패딩
                    audio_bytes += b'\x00' * (required_bytes - len(audio_bytes))
                elif len(audio_bytes) > required_bytes:
                    # 데이터가 많으면 자르기
                    audio_bytes = audio_bytes[:required_bytes]

                return (audio_bytes, pyaudio.paContinue)
            else:
                # 큐가 비어있으면 무음 출력
                silence = b'\x00' * (frame_count * config.CHANNELS * 2)
                return (silence, pyaudio.paContinue)

        except Exception as e:
            logger.error(f"Error in speaker callback: {e}")
            # 에러 시 무음 출력
            silence = b'\x00' * (frame_count * config.CHANNELS * 2)
            return (silence, pyaudio.paContinue)

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
                logger.debug(f"📊 Published status: {status}")
            except Exception as e:
                logger.error(f"Error publishing status: {e}")

    def start(self):
        """오디오 캡처 및 전송 시작"""
        logger.info("🚀 Starting GOYO Audio Client...")

        # 디바이스 목록 출력
        self.list_audio_devices()

        # MQTT 연결
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT, exiting")
            return False

        # 오디오 스트림 열기
        if not self.open_streams():
            logger.error("Failed to open audio streams, exiting")
            return False

        # 스트림 시작
        self.is_running = True
        self.reference_stream.start_stream()
        if self.error_stream:
            self.error_stream.start_stream()
        if self.speaker_stream:
            self.speaker_stream.start_stream()

        logger.info("🎤 Audio capture started")
        logger.info("🔊 Speaker output started")
        logger.info("Press Ctrl+C to stop")

        # 메인 루프
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")

        return True

    def stop(self):
        """오디오 캡처 중지"""
        logger.info("🛑 Stopping audio client...")
        self.is_running = False

        # 스트림 중지
        if self.reference_stream:
            self.reference_stream.stop_stream()
            self.reference_stream.close()
        if self.error_stream:
            self.error_stream.stop_stream()
            self.error_stream.close()
        if self.speaker_stream:
            self.speaker_stream.stop_stream()
            self.speaker_stream.close()

        # PyAudio 종료
        self.pyaudio.terminate()

        # 큐 비우기
        while not self.speaker_queue.empty():
            try:
                self.speaker_queue.get_nowait()
            except:
                break

        # MQTT 연결 해제
        if self.mqtt_client:
            self.publish_status("offline")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

        logger.info("✅ Audio client stopped")

    def cleanup(self, signum, frame):
        """Signal handler for graceful shutdown"""
        logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)


def main():
    """메인 함수"""
    client = AudioClient()

    # Signal handlers
    signal.signal(signal.SIGINT, client.cleanup)
    signal.signal(signal.SIGTERM, client.cleanup)

    # 시작
    client.start()


if __name__ == "__main__":
    main()
