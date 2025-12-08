#!/usr/bin/env python3
"""
alsaaudio로 두 마이크 동시 캡처 + MQTT 스트리밍 테스트
"""
import alsaaudio
import paho.mqtt.client as mqtt
import json
import struct
import time
import threading
import os

CONFIG_FILE = os.path.expanduser("~/goyo/goyo_config.json")

SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK_SIZE = 48000  

REFERENCE_MIC = "hw:4,0"  
ERROR_MIC = "hw:3,0"  

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

USER_ID = config['user_id']
MQTT_HOST = config['mqtt_broker_host']
MQTT_PORT = config['mqtt_broker_port']
MQTT_USER = config['mqtt_username']
MQTT_PASS = config['mqtt_password']

mqtt_client = mqtt.Client(client_id=f"test_alsaaudio_{USER_ID}")
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

print(f"MQTT 연결: {MQTT_HOST}:{MQTT_PORT}")

ref_config_topic = f"mqtt/audio/reference/{USER_ID}/config"
err_config_topic = f"mqtt/audio/error/{USER_ID}/config"

config_msg = json.dumps({
    "sample_rate": SAMPLE_RATE,
    "channels": CHANNELS,
    "chunk_size": CHUNK_SIZE,
    "format": "int16"
})

mqtt_client.publish(ref_config_topic, config_msg, qos=1, retain=True)
mqtt_client.publish(err_config_topic, config_msg, qos=1, retain=True)
print(f"Config 발행 완료")

print(f"\n마이크 열기...")

reference_mic = alsaaudio.PCM(
    alsaaudio.PCM_CAPTURE,
    device=REFERENCE_MIC,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    format=alsaaudio.PCM_FORMAT_S16_LE,
    periodsize=CHUNK_SIZE
)
print(f"Reference 마이크 열림: {REFERENCE_MIC}")

error_mic = alsaaudio.PCM(
    alsaaudio.PCM_CAPTURE,
    device=ERROR_MIC,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    format=alsaaudio.PCM_FORMAT_S16_LE,
    periodsize=CHUNK_SIZE
)
print(f"Error 마이크 열림: {ERROR_MIC}")

def stream_mic(mic, topic_prefix, mic_name):
    """마이크 스트리밍 스레드"""
    sequence = 0
    audio_topic = f"{topic_prefix}/stream"

    print(f"{mic_name} 스트리밍 시작: {audio_topic}")

    start_time = time.time()
    duration = 10  

    while (time.time() - start_time) < duration:
        
        length, audio_data = mic.read()

        if length > 0:
            
            payload = struct.pack('<I', sequence) + audio_data

            
            mqtt_client.publish(audio_topic, payload, qos=0)
            sequence += 1

            if sequence % 10 == 0:
                print(f"{mic_name}: {sequence} 청크 전송")

    print(f"{mic_name} 스트리밍 완료: {sequence} 청크")

ref_thread = threading.Thread(
    target=stream_mic,
    args=(reference_mic, f"mqtt/audio/reference/{USER_ID}", "Reference")
)

err_thread = threading.Thread(
    target=stream_mic,
    args=(error_mic, f"mqtt/audio/error/{USER_ID}", "Error")
)

print(f"\n10초 스트리밍 시작...\n")

ref_thread.start()
err_thread.start()

ref_thread.join()
err_thread.join()

reference_mic.close()
error_mic.close()
mqtt_client.loop_stop()
mqtt_client.disconnect()

print(f"\n테스트 완료!")
