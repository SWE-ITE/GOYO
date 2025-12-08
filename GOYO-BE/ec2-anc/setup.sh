#!/bin/bash
# GOYO AI Server Setup Script
# EC2 #2 (AI Server)

set -e

echo "========================================="
echo "GOYO AI Server Setup"
echo "========================================="

# 1. .env 파일 생성
echo ""
echo "Step 1: Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo " .env file created from .env.example"
    echo " Please edit .env and update:"
    echo "     - REDIS_HOST (EC2 #1 Private IP)"
    echo "     - MQTT_BROKER_HOST (EC2 #1 Private IP)"
else
    echo " .env file already exists"
fi

# 2. 네트워크 테스트
echo ""
echo "Step 2: Testing network connectivity..."
REDIS_HOST=$(grep REDIS_HOST .env | cut -d '=' -f2 | tr -d '<>')
MQTT_HOST=$(grep MQTT_BROKER_HOST .env | cut -d '=' -f2 | tr -d '<>')

if [[ "$REDIS_HOST" == *"BACKEND-PRIVATE-IP"* ]]; then
    echo " REDIS_HOST not configured yet"
else
    echo "Testing Redis connection to $REDIS_HOST:6379..."
    timeout 3 bash -c "cat < /dev/null > /dev/tcp/$REDIS_HOST/6379" && echo " Redis reachable" || echo "❌ Redis not reachable"
fi

if [[ "$MQTT_HOST" == *"BACKEND-PRIVATE-IP"* ]]; then
    echo " MQTT_BROKER_HOST not configured yet"
else
    echo "Testing MQTT connection to $MQTT_HOST:1883..."
    timeout 3 bash -c "cat < /dev/null > /dev/tcp/$MQTT_HOST/1883" && echo " MQTT reachable" || echo "❌ MQTT not reachable"
fi

echo ""
echo "========================================="
echo "Setup completed!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file and update Backend Private IP"
echo "2. Run: docker-compose up -d"
echo "3. Check logs: docker-compose logs -f"
echo "4. Test health: curl http://localhost:8001/health"
echo ""
