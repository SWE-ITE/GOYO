#!/usr/bin/env python3
"""
간단한 MQTT 연결 테스트 스크립트
PyAudio 없이 MQTT 연결만 테스트
"""
import json
import os
import time
import paho.mqtt.client as mqtt

CONFIG_FILE = os.path.expanduser("~/goyo/goyo_config.json")

def load_config():
    """설정 파일 로드"""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def on_connect(client, userdata, flags, rc):
    """MQTT 연결 콜백"""
    if rc == 0:
        print(f"MQTT 브로커 연결 성공!")
        
        client.publish("test/raspberry-pi", "Hello from Raspberry Pi!")
        print("테스트 메시지 발행: test/raspberry-pi")
    else:
        print(f"MQTT 연결 실패 (rc: {rc})")

def on_disconnect(client, userdata, rc):
    """MQTT 연결 해제 콜백"""
    print(f"⚠️ MQTT 연결 해제 (rc: {rc})")

def on_publish(client, userdata, mid):
    """메시지 발행 콜백"""
    print(f"메시지 발행 완료 (mid: {mid})")

def main():
    print("🔧 MQTT 연결 테스트 시작...")

    
    config = load_config()
    print(f"설정: {config['mqtt_broker_host']}:{config['mqtt_broker_port']}")
    print(f"👤 사용자: {config['mqtt_username']}")

    
    client = mqtt.Client(client_id=f"test_client_{config['user_id']}")
    client.username_pw_set(config['mqtt_username'], config['mqtt_password'])

    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    
    try:
        print(f"연결 시도: {config['mqtt_broker_host']}:{config['mqtt_broker_port']}")
        client.connect(config['mqtt_broker_host'], config['mqtt_broker_port'], 60)

        
        client.loop_start()
        time.sleep(5)
        client.loop_stop()

        
        client.disconnect()
        print("테스트 완료!")

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
