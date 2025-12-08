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

CONFIG_FILE = os.path.expanduser("~/goyo/goyo_config.json")

SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK_SIZE = 4800  

def load_config():
    """설정 파일 로드"""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def on_connect(client, userdata, flags, rc):
    """MQTT 연결 콜백"""
    if rc == 0:
        print(f"MQTT 브로커 연결 성공!")
        userdata['connected'] = True
    else:
        print(f"MQTT 연결 실패 (rc: {rc})")
        userdata['connected'] = False

def on_disconnect(client, userdata, rc):
    """MQTT 연결 해제 콜백"""
    print(f"⚠️ MQTT 연결 해제 (rc: {rc})")
    userdata['connected'] = False

def on_publish(client, userdata, mid):
    """메시지 발행 콜백"""
    userdata['publish_count'] += 1
    if userdata['publish_count'] % 10 == 0:
        print(f"{userdata['publish_count']} 청크 전송됨")

def main():
    print("오디오 스트리밍 테스트 시작...")

    
    config = load_config()
    user_id = config['user_id']
    print(f"User ID: {user_id}")
    print(f"MQTT: {config['mqtt_broker_host']}:{config['mqtt_broker_port']}")
    print(f"Sample Rate: {SAMPLE_RATE}Hz, Chunk: {CHUNK_SIZE} samples (0.1초)")

    
    userdata = {'connected': False, 'publish_count': 0}
    client = mqtt.Client(client_id=f"test_audio_{user_id}", userdata=userdata)
    client.username_pw_set(config['mqtt_username'], config['mqtt_password'])
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    
    try:
        print(f"MQTT 연결 시도...")
        client.connect(config['mqtt_broker_host'], config['mqtt_broker_port'], 60)
        client.loop_start()

        
        timeout = 5
        start_time = time.time()
        while not userdata['connected'] and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if not userdata['connected']:
            print("MQTT 연결 실패 (타임아웃)")
            return

        
        audio_topic = f"mqtt/audio/reference/{user_id}/stream"
        config_topic = f"mqtt/audio/reference/{user_id}/config"

        
        config_msg = json.dumps({
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "chunk_size": CHUNK_SIZE,
            "format": "int16"
        })
        client.publish(config_topic, config_msg, qos=1, retain=True)
        print(f"Config 발행: {config_topic}")

        
        
        
        
        
        
        arecord_cmd = [
            'arecord',
            '-D', 'hw:4,0',  
            '-f', 'S16_LE',
            '-r', str(SAMPLE_RATE),
            '-c', str(CHANNELS),
            '-t', 'raw'
        ]

        print(f"오디오 캡처 시작: {' '.join(arecord_cmd)}")
        print("⏱️  10초간 스트리밍...")

        
        process = subprocess.Popen(
            arecord_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=CHUNK_SIZE * 2  
        )

        sequence = 0
        chunk_bytes = CHUNK_SIZE * 2  
        start_time = time.time()
        duration = 10  

        while (time.time() - start_time) < duration:
            
            audio_data = process.stdout.read(chunk_bytes)

            if len(audio_data) != chunk_bytes:
                print(f"⚠️ 불완전한 청크: {len(audio_data)} bytes")
                break

            
            payload = struct.pack('<I', sequence) + audio_data

            
            client.publish(audio_topic, payload, qos=0)

            sequence += 1

        
        process.terminate()
        process.wait()

        print(f"\n스트리밍 완료!")
        print(f"총 {userdata['publish_count']}개 청크 전송")
        print(f"총 {userdata['publish_count'] * 0.1:.1f}초 오디오")

        
        time.sleep(1)
        client.loop_stop()
        client.disconnect()

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
