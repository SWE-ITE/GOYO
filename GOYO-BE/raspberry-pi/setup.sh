#!/bin/bash
# GOYO Raspberry Pi Setup Script

set -e

echo "========================================="
echo "GOYO Raspberry Pi Setup"
echo "========================================="

# 1. 시스템 업데이트
echo ""
echo "Step 1: Updating system..."
sudo apt update
sudo apt upgrade -y

# 2. 의존성 설치
echo ""
echo "Step 2: Installing dependencies..."
sudo apt install -y python3-pip python3-dev portaudio19-dev git

# 3. Python 패키지 설치
echo ""
echo "Step 3: Installing Python packages..."
pip3 install -r requirements.txt

# 4. .env 파일 생성
echo ""
echo "Step 4: Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo " .env file created from .env.example"
    echo " Please edit .env and update:"
    echo "     - MQTT_BROKER_HOST (EC2 #1 Public IP)"
    echo "     - USER_ID (Backend 사용자 ID)"
    echo "     - SOURCE_MIC_INDEX, REFERENCE_MIC_INDEX"
else
    echo " .env file already exists"
fi

# 5. 오디오 디바이스 확인
echo ""
echo "Step 5: Checking audio devices..."
echo "Available audio input devices:"
arecord -l

echo ""
echo "PyAudio device list:"
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'{i}: {info[\"name\"]} (Inputs: {info[\"maxInputChannels\"]})')
"

# 6. 실행 권한 부여
echo ""
echo "Step 6: Setting permissions..."
chmod +x audio_client.py
chmod +x start.sh
chmod +x stop.sh

echo ""
echo "========================================="
echo "Setup completed!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file:"
echo "   nano .env"
echo ""
echo "2. Test audio client:"
echo "   ./audio_client.py"
echo ""
echo "3. Install as systemd service (optional):"
echo "   sudo cp goyo-audio.service /etc/systemd/system/"
echo "   sudo systemctl enable goyo-audio"
echo "   sudo systemctl start goyo-audio"
echo ""
