#!/bin/bash
# GOYO Backend Stack Setup Script
# EC2 #1 (Backend Server)

set -e

echo "========================================="
echo "GOYO Backend Stack Setup"
echo "========================================="

# 1. MQTT 비밀번호 파일 생성
echo ""
echo "Step 1: Creating MQTT password file..."
docker run -it --rm -v $(pwd)/mosquitto/config:/config eclipse-mosquitto:2.0 mosquitto_passwd -c -b /config/passwd goyo_backend backend_mqtt_pass_2025
docker run -it --rm -v $(pwd)/mosquitto/config:/config eclipse-mosquitto:2.0 mosquitto_passwd -b /config/passwd raspberry_pi raspi_mqtt_pass_2025
docker run -it --rm -v $(pwd)/mosquitto/config:/config eclipse-mosquitto:2.0 mosquitto_passwd -b /config/passwd ai_server ai_mqtt_pass_2025

echo " MQTT users created:"
echo "   - goyo_backend / backend_mqtt_pass_2025"
echo "   - raspberry_pi / raspi_mqtt_pass_2025"
echo "   - ai_server / ai_mqtt_pass_2025"

# 2. .env 파일 생성
echo ""
echo "Step 2: Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo " .env file created from .env.example"
    echo " Please edit .env and update AI_SERVER_HOST with EC2 #2 Private IP"
else
    echo " .env file already exists"
fi

# 3. 디렉토리 권한 설정
echo ""
echo "Step 3: Setting directory permissions..."
chmod -R 755 mosquitto/
sudo chown -R 1883:1883 mosquitto/data mosquitto/log 2>/dev/null || true

# 4. Docker 네트워크 확인
echo ""
echo "Step 4: Checking Docker network..."
docker network create goyo_network 2>/dev/null || echo " Network already exists"

echo ""
echo "========================================="
echo "Setup completed!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file and update AI_SERVER_HOST"
echo "2. Run: docker-compose up -d"
echo "3. Check logs: docker-compose logs -f"
echo ""
