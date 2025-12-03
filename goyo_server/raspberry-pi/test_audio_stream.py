#!/usr/bin/env python3
"""
간단한 오디오 스트리밍 테스트
arecord로 오디오 캡처 → MQTT 전송
"""
import json
import os
import subprocess
import time
import struct
import paho.mqtt.client as mqtt

# 설정 파일 로드
CONFIG_FILE = os.path.expanduser("~/goyo/goyo_config.json")

# 오디오 설정
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK_SIZE = 4800  # 0.1초 (48000 / 10)

def load_config():
    """설정 파일 로드"""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def on_connect(client, userdata, flags, rc):
    """MQTT 연결 콜백"""
    if rc == 0:
        print(f"✅ MQTT 브로커 연결 성공!")
        userdata['connected'] = True
    else:
        print(f"❌ MQTT 연결 실패 (rc: {rc})")
        userdata['connected'] = False

def on_disconnect(client, userdata, rc):
    """MQTT 연결 해제 콜백"""
    print(f"⚠️ MQTT 연결 해제 (rc: {rc})")
    userdata['connected'] = False

def on_publish(client, userdata, mid):
    """메시지 발행 콜백"""
    userdata['publish_count'] += 1
    if userdata['publish_count'] % 10 == 0:
        print(f"📤 {userdata['publish_count']} 청크 전송됨")

def main():
    print("🎤 오디오 스트리밍 테스트 시작...")

    # 설정 로드
    config = load_config()
    user_id = config['user_id']
    print(f"📋 User ID: {user_id}")
    print(f"📋 MQTT: {config['mqtt_broker_host']}:{config['mqtt_broker_port']}")
    print(f"🎵 Sample Rate: {SAMPLE_RATE}Hz, Chunk: {CHUNK_SIZE} samples (0.1초)")

    # MQTT 클라이언트 생성
    userdata = {'connected': False, 'publish_count': 0}
    client = mqtt.Client(client_id=f"test_audio_{user_id}", userdata=userdata)
    client.username_pw_set(config['mqtt_username'], config['mqtt_password'])
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    # MQTT 연결
    try:
        print(f"🔌 MQTT 연결 시도...")
        client.connect(config['mqtt_broker_host'], config['mqtt_broker_port'], 60)
        client.loop_start()

        # 연결 대기
        timeout = 5
        start_time = time.time()
        while not userdata['connected'] and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if not userdata['connected']:
            print("❌ MQTT 연결 실패 (타임아웃)")
            return

        # MQTT 토픽
        audio_topic = f"mqtt/audio/reference/{user_id}/stream"
        config_topic = f"mqtt/audio/reference/{user_id}/config"

        # Config 메시지 발행
        config_msg = json.dumps({
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "chunk_size": CHUNK_SIZE,
            "format": "int16"
        })
        client.publish(config_topic, config_msg, qos=1, retain=True)
        print(f"📤 Config 발행: {config_topic}")

        # arecord 프로세스 시작
        # -D hw:2,0: 디바이스 (PROGRESS_LOG.md 참고)
        # -f S16_LE: 16bit Little Endian
        # -r 48000: 48kHz
        # -c 1: Mono
        # -t raw: RAW PCM 출력
        arecord_cmd = [
            'arecord',
            '-D', 'hw:4,0',  # USB 마이크 (ABKO MP3300)
            '-f', 'S16_LE',
            '-r', str(SAMPLE_RATE),
            '-c', str(CHANNELS),
            '-t', 'raw'
        ]

        print(f"🎤 오디오 캡처 시작: {' '.join(arecord_cmd)}")
        print("⏱️  10초간 스트리밍...")

        # arecord 실행
        process = subprocess.Popen(
            arecord_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=CHUNK_SIZE * 2  # 16bit = 2 bytes per sample
        )

        sequence = 0
        chunk_bytes = CHUNK_SIZE * 2  # 16bit = 2 bytes per sample
        start_time = time.time()
        duration = 10  # 10초 테스트

        while (time.time() - start_time) < duration:
            # 청크 읽기
            audio_data = process.stdout.read(chunk_bytes)

            if len(audio_data) != chunk_bytes:
                print(f"⚠️ 불완전한 청크: {len(audio_data)} bytes")
                break

            # Binary payload: [4 bytes: sequence] + [audio bytes]
            payload = struct.pack('<I', sequence) + audio_data

            # MQTT 전송
            client.publish(audio_topic, payload, qos=0)

            sequence += 1

        # 종료
        process.terminate()
        process.wait()

        print(f"\n✅ 스트리밍 완료!")
        print(f"📊 총 {userdata['publish_count']}개 청크 전송")
        print(f"📊 총 {userdata['publish_count'] * 0.1:.1f}초 오디오")

        # MQTT 종료
        time.sleep(1)
        client.loop_stop()
        client.disconnect()

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
