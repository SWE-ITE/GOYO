#!/usr/bin/env python3
"""
GOYO Device Server
라즈베리파이 디바이스 검색 및 설정을 위한 HTTP 서버 + mDNS 서비스
"""
from flask import Flask, request, jsonify
from zeroconf import ServiceInfo, Zeroconf
import socket
import json
import logging
import signal
import sys
import os
from threading import Thread

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# MQTT 설정 저장 경로
CONFIG_FILE = "/home/hoyoungchung/goyo/goyo_config.json"

# mDNS 서비스
zeroconf = None
service_info = None


def get_device_id():
    """라즈베리파이 고유 ID 생성 (시리얼 번호 기반)"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    serial = line.split(':')[1].strip()
                    return f"goyo-rpi-{serial[-4:]}"
    except:
        pass
    return "goyo-rpi-0000"


def get_local_ip():
    """로컬 IP 주소 가져오기 (여러 방법 시도)"""
    # 방법 1: Google DNS로 연결해서 로컬 IP 감지
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except:
        pass

    # 방법 2: hostname -I 명령어 사용 (Raspberry Pi)
    try:
        import subprocess
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
        ips = result.stdout.strip().split()
        if ips and not ips[0].startswith('127.'):
            return ips[0]
    except:
        pass

    # 방법 3: hostname으로 시도
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip
    except:
        pass

    return "127.0.0.1"


def register_mdns_service():
    """mDNS 서비스 등록 (_goyo._tcp.local.)"""
    global zeroconf, service_info

    device_id = get_device_id()
    local_ip = get_local_ip()

    logger.info(f"🔍 Registering mDNS service: {device_id}")
    logger.info(f"   IP Address: {local_ip}")

    # Zeroconf 초기화
    zeroconf = Zeroconf()

    # 서비스 정보
    service_type = "_goyo._tcp.local."
    service_name = f"{device_id}.{service_type}"

    properties = {
        b'name': b'GOYO Device',
        b'version': b'1.0',
        b'device_type': b'goyo_device'
    }

    service_info = ServiceInfo(
        service_type,
        service_name,
        addresses=[socket.inet_aton(local_ip)],
        port=5000,  # HTTP 서버 포트
        properties=properties,
        server=f"{device_id}.local."
    )

    zeroconf.register_service(service_info)
    logger.info(f"✅ mDNS service registered: {service_name}")


def unregister_mdns_service():
    """mDNS 서비스 해제"""
    global zeroconf, service_info
    if zeroconf and service_info:
        logger.info("🛑 Unregistering mDNS service...")
        zeroconf.unregister_service(service_info)
        zeroconf.close()
        logger.info("✅ mDNS service unregistered")


@app.route('/configure', methods=['POST'])
def configure():
    """
    백엔드에서 MQTT 브로커 설정 수신

    Request Body:
    {
        "mqtt_broker_host": "mqtt.example.com",
        "mqtt_broker_port": 1883,
        "mqtt_username": "user",
        "mqtt_password": "pass",
        "user_id": "123"
    }
    """
    try:
        config_data = request.get_json()
        logger.info(f"📥 Received MQTT configuration")

        # 필수 필드 검증
        required_fields = ['mqtt_broker_host', 'mqtt_broker_port', 'user_id']
        for field in required_fields:
            if field not in config_data:
                return jsonify({
                    "error": f"Missing required field: {field}"
                }), 400

        # 설정 파일에 저장
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)

        logger.info(f"✅ MQTT configuration saved to {CONFIG_FILE}")
        logger.info(f"   Broker: {config_data['mqtt_broker_host']}:{config_data['mqtt_broker_port']}")
        logger.info(f"   User ID: {config_data['user_id']}")

        # audio_client를 재시작하여 새 설정 적용
        # systemctl restart goyo-audio (서비스로 실행 시)
        logger.info("ℹ️  Restart audio_client to apply new configuration")

        return jsonify({
            "message": "Configuration saved successfully",
            "device_id": get_device_id(),
            "restart_required": True
        }), 200

    except Exception as e:
        logger.error(f"❌ Configuration error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    """디바이스 상태 조회"""
    device_id = get_device_id()
    local_ip = get_local_ip()

    # 설정 파일 확인
    config_exists = os.path.exists(CONFIG_FILE)
    mqtt_configured = False

    if config_exists:
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                mqtt_configured = all(
                    k in config for k in ['mqtt_broker_host', 'mqtt_broker_port', 'user_id']
                )
        except:
            pass

    return jsonify({
        "device_id": device_id,
        "device_name": "GOYO Device",
        "device_type": "goyo_device",
        "ip_address": local_ip,
        "mqtt_configured": mqtt_configured,
        "components": {
            "reference_mic": True,
            "error_mic": True,
            "speaker": True
        }
    }), 200


@app.route('/health', methods=['GET'])
def health():
    """헬스 체크"""
    return jsonify({"status": "healthy"}), 200


def signal_handler(sig, frame):
    """종료 시그널 처리"""
    logger.info("🛑 Shutting down device server...")
    unregister_mdns_service()
    sys.exit(0)


def main():
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # mDNS 서비스 등록
    register_mdns_service()

    # Flask 서버 실행
    logger.info("🚀 Starting GOYO Device Server on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    main()
