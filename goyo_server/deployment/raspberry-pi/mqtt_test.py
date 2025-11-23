#!/usr/bin/env python3
"""
MQTT 연결 테스트 스크립트 (오디오 하드웨어 없이 테스트)
"""
import paho.mqtt.client as mqtt
import json
import time
import sys
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 설정 파일 경로
CONFIG_FILE = "/home/hoyoungchung/goyo/goyo_config.json"

def load_config():
    """설정 파일 로드"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        logger.info(f"✅ 설정 파일 로드 성공: {CONFIG_FILE}")
        return config
    except Exception as e:
        logger.error(f"❌ 설정 파일 로드 실패: {e}")
        sys.exit(1)

def on_connect(client, userdata, flags, rc):
    """MQTT 연결 콜백"""
    if rc == 0:
        logger.info("✅ MQTT 브로커 연결 성공!")

        # 안티노이즈 토픽 구독
        user_id = userdata['user_id']
        topic = f"goyo/user_{user_id}/antinoise"
        client.subscribe(topic)
        logger.info(f"✅ 토픽 구독: {topic}")

        # 테스트 메시지 발행
        test_topic = f"goyo/user_{user_id}/reference"
        client.publish(test_topic, "Test message from Raspberry Pi")
        logger.info(f"📤 테스트 메시지 발행: {test_topic}")

    else:
        logger.error(f"❌ MQTT 연결 실패 (코드: {rc})")
        logger.error(f"   0: 성공")
        logger.error(f"   1: 잘못된 프로토콜 버전")
        logger.error(f"   2: 잘못된 클라이언트 ID")
        logger.error(f"   3: 서버 사용 불가")
        logger.error(f"   4: 잘못된 사용자 이름 또는 비밀번호")
        logger.error(f"   5: 권한 없음")

def on_disconnect(client, userdata, rc):
    """MQTT 연결 해제 콜백"""
    if rc != 0:
        logger.warning(f"⚠️  예기치 않은 연결 해제 (코드: {rc})")
    else:
        logger.info("✅ MQTT 브로커 연결 해제")

def on_message(client, userdata, msg):
    """메시지 수신 콜백"""
    logger.info(f"📥 메시지 수신:")
    logger.info(f"   토픽: {msg.topic}")
    logger.info(f"   페이로드 크기: {len(msg.payload)} bytes")

def on_subscribe(client, userdata, mid, granted_qos):
    """구독 성공 콜백"""
    logger.info(f"✅ 구독 확인 (QoS: {granted_qos})")

def main():
    # 설정 로드
    config = load_config()

    # MQTT 클라이언트 생성
    device_id = "goyo-rpi-test"
    client = mqtt.Client(client_id=device_id, userdata={'user_id': config['user_id']})

    # 콜백 설정
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.on_subscribe = on_subscribe

    # 인증 설정 (필요시)
    if config.get('mqtt_username'):
        client.username_pw_set(config['mqtt_username'], config.get('mqtt_password', ''))
        logger.info(f"🔐 인증 설정: {config['mqtt_username']}")

    # 연결 시도
    broker_host = config['mqtt_broker_host']
    broker_port = config['mqtt_broker_port']

    logger.info(f"🔌 MQTT 브로커 연결 시도...")
    logger.info(f"   호스트: {broker_host}")
    logger.info(f"   포트: {broker_port}")
    logger.info(f"   사용자 ID: {config['user_id']}")

    try:
        client.connect(broker_host, broker_port, 60)
        logger.info("✅ 연결 요청 전송")

        # 메시지 루프 시작
        logger.info("📡 MQTT 메시지 루프 시작 (Ctrl+C로 종료)")
        client.loop_forever()

    except KeyboardInterrupt:
        logger.info("\n⏹️  사용자 중단")
        client.disconnect()

    except Exception as e:
        logger.error(f"❌ 연결 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
