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

MQTT_BROKER = "3.36.205.186"
MQTT_PORT = 1883
MQTT_USERNAME = "goyo_backend"
MQTT_PASSWORD = "backend_mqtt_pass_2025"
USER_ID = "9"

latencies = deque(maxlen=100)
sequence_sent = {}  


def on_connect(client, userdata, flags, rc):
    """MQTT 연결"""
    if rc == 0:
        print("Connected to MQTT Broker")

        
        client.subscribe(f"mqtt/speaker/output/{USER_ID}/stream", qos=0)
        print(f"Subscribed to mqtt/speaker/output/{USER_ID}/stream")
    else:
        print(f"Connection failed: {rc}")


def on_message(client, userdata, msg):
    """안티노이즈 수신 - 딜레이 측정"""
    try:
        
        if len(msg.payload) < 4:
            return

        recv_seq = struct.unpack('<I', msg.payload[:4])[0]
        recv_time = time.time()

        
        if recv_seq in sequence_sent:
            send_time = sequence_sent[recv_seq]
            latency_ms = (recv_time - send_time) * 1000

            latencies.append(latency_ms)

            
            if len(latencies) > 0:
                avg_latency = np.mean(latencies)
                min_latency = np.min(latencies)
                max_latency = np.max(latencies)
                std_latency = np.std(latencies)

                print(f"Seq {recv_seq}: {latency_ms:.1f}ms | "
                      f"Avg: {avg_latency:.1f}ms | "
                      f"Min: {min_latency:.1f}ms | "
                      f"Max: {max_latency:.1f}ms | "
                      f"Std: {std_latency:.1f}ms")

            
            del sequence_sent[recv_seq]

    except Exception as e:
        print(f"Error: {e}")


def send_test_audio(client, sequence):
    """테스트 오디오 전송"""
    try:
        
        sample_rate = 16000
        duration = 1.0
        frequency = 440  

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * frequency * t)
        audio_int16 = (audio_float * 32767).astype(np.int16)

        
        payload = struct.pack('<I', sequence) + audio_int16.tobytes()

        
        send_time = time.time()
        sequence_sent[sequence] = send_time

        
        client.publish(
            f"mqtt/audio/reference/{USER_ID}/stream",
            payload,
            qos=0
        )

        print(f"Sent test audio: seq={sequence}, {len(audio_int16)} samples")

    except Exception as e:
        print(f"Error sending: {e}")


def main():
    """메인 함수"""
    print("GOYO Latency Test Starting...")
    print(f"   MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"   User ID: {USER_ID}")
    print()

    
    client = mqtt.Client(client_id="goyo-latency-test")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    
    print("Connecting to MQTT Broker...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    
    time.sleep(2)

    
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
    print("Sent config message\n")

    
    print("Starting latency measurement...")
    print("-" * 80)

    try:
        for seq in range(10):
            send_test_audio(client, seq)
            time.sleep(1.2)  

        
        print("\n⏳ Waiting for final responses...")
        time.sleep(3)

        
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
            print("\nNo responses received!")
            print("   Check:")
            print("   1. ANC server is running")
            print("   2. MQTT broker is accessible")
            print("   3. User ID is correct")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")

    
    client.loop_stop()
    client.disconnect()
    print("\nTest completed")


if __name__ == "__main__":
    main()
