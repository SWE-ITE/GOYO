#!/usr/bin/env python3
"""
GOYO 오디오 스트리밍 지연시간 측정 테스트
라즈베리파이 → MQTT → ANC 서버 → MQTT → 라즈베리파이
"""
import paho.mqtt.client as mqtt
import json
import struct
import time
import numpy as np
from collections import deque

# 설정
MQTT_BROKER = "3.36.205.186"
MQTT_PORT = 1883
MQTT_USERNAME = "goyo_backend"
MQTT_PASSWORD = "backend_mqtt_pass_2025"
USER_ID = "1"

# 통계
latencies = deque(maxlen=100)
sequence_sent = {}  # {seq: timestamp}


def on_connect(client, userdata, flags, rc):
    """MQTT 연결"""
    if rc == 0:
        print("✅ Connected to MQTT Broker")

        # 안티노이즈 스트림 구독 (응답 확인용)
        client.subscribe(f"mqtt/speaker/output/{USER_ID}/stream", qos=0)
        print(f"📡 Subscribed to mqtt/speaker/output/{USER_ID}/stream")
    else:
        print(f"❌ Connection failed: {rc}")


def on_message(client, userdata, msg):
    """안티노이즈 수신 - 딜레이 측정"""
    try:
        # Binary Payload: [4 bytes: sequence] + [audio]
        if len(msg.payload) < 4:
            return

        recv_seq = struct.unpack('<I', msg.payload[:4])[0]
        recv_time = time.time()

        # 해당 sequence를 보낸 시간 찾기
        if recv_seq in sequence_sent:
            send_time = sequence_sent[recv_seq]
            latency_ms = (recv_time - send_time) * 1000

            latencies.append(latency_ms)

            # 통계 출력
            if len(latencies) > 0:
                avg_latency = np.mean(latencies)
                min_latency = np.min(latencies)
                max_latency = np.max(latencies)
                std_latency = np.std(latencies)

                print(f"🔄 Seq {recv_seq}: {latency_ms:.1f}ms | "
                      f"Avg: {avg_latency:.1f}ms | "
                      f"Min: {min_latency:.1f}ms | "
                      f"Max: {max_latency:.1f}ms | "
                      f"Std: {std_latency:.1f}ms")

            # 메모리 정리 (오래된 sequence 제거)
            del sequence_sent[recv_seq]

    except Exception as e:
        print(f"❌ Error: {e}")


def send_test_audio(client, sequence):
    """테스트 오디오 전송"""
    try:
        # 테스트 오디오 생성 (1초, 16kHz, 440Hz 사인파)
        sample_rate = 16000
        duration = 1.0
        frequency = 440  # A4 note

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * frequency * t)
        audio_int16 = (audio_float * 32767).astype(np.int16)

        # Binary Payload: [4 bytes: sequence] + [PCM16 audio]
        payload = struct.pack('<I', sequence) + audio_int16.tobytes()

        # 전송 시간 기록
        send_time = time.time()
        sequence_sent[sequence] = send_time

        # MQTT 발행
        client.publish(
            f"mqtt/audio/reference/{USER_ID}/stream",
            payload,
            qos=0
        )

        print(f"📤 Sent test audio: seq={sequence}, {len(audio_int16)} samples")

    except Exception as e:
        print(f"❌ Error sending: {e}")


def main():
    """메인 함수"""
    print("🚀 GOYO Latency Test Starting...")
    print(f"   MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"   User ID: {USER_ID}")
    print()

    # MQTT 클라이언트 초기화
    client = mqtt.Client(client_id="goyo-latency-test")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    # 연결
    print("Connecting to MQTT Broker...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    # 연결 대기
    time.sleep(2)

    # Config 메시지 전송 (한 번만)
    config = {
        "sr": 16000,
        "ch": 1,
        "dt": "i16",
        "cs": 16000
    }
    client.publish(
        f"mqtt/audio/reference/{USER_ID}/config",
        json.dumps(config),
        qos=1,
        retain=True
    )
    print("📡 Sent config message\n")

    # 테스트 오디오 전송 (10번)
    print("📊 Starting latency measurement...")
    print("-" * 80)

    try:
        for seq in range(10):
            send_test_audio(client, seq)
            time.sleep(1.2)  # 1.2초 간격 (1초 오디오 + 0.2초 여유)

        # 마지막 응답 대기
        print("\n⏳ Waiting for final responses...")
        time.sleep(3)

        # 최종 통계
        if len(latencies) > 0:
            print("\n" + "=" * 80)
            print("📈 Final Statistics:")
            print(f"   Total samples: {len(latencies)}")
            print(f"   Average latency: {np.mean(latencies):.1f} ms")
            print(f"   Min latency: {np.min(latencies):.1f} ms")
            print(f"   Max latency: {np.max(latencies):.1f} ms")
            print(f"   Std deviation: {np.std(latencies):.1f} ms")
            print(f"   Median: {np.median(latencies):.1f} ms")
            print("=" * 80)
        else:
            print("\n❌ No responses received!")
            print("   Check:")
            print("   1. ANC server is running")
            print("   2. MQTT broker is accessible")
            print("   3. User ID is correct")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")

    # 정리
    client.loop_stop()
    client.disconnect()
    print("\n✅ Test completed")


if __name__ == "__main__":
    main()
