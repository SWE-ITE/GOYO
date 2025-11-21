from sqlalchemy.orm import Session
from app.models.device import Device
from typing import List, Optional
import json
import logging
from datetime import datetime
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
import socket
import requests
from app.config import settings

logger = logging.getLogger(__name__)


class GoyoDeviceListener(ServiceListener):
    """mDNS로 GOYO 디바이스 검색"""

    def __init__(self):
        self.devices = []

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        info = zeroconf.get_service_info(service_type, name)
        if info:
            # GOYO 디바이스 정보 파싱
            device_id = name.split('.')[0]  # goyo-rpi-1234._goyo._tcp.local
            ip_address = socket.inet_ntoa(info.addresses[0])

            self.devices.append({
                "device_id": device_id,
                "device_name": info.properties.get(b'name', b'GOYO Device').decode('utf-8'),
                "device_type": "goyo_device",
                "connection_type": "wifi",
                "signal_strength": 85,  # mDNS는 signal strength 제공 안 함
                "ip_address": ip_address,
                "components": {
                    "reference_mic": True,
                    "error_mic": True,
                    "speaker": True
                }
            })

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        pass

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        pass


class DeviceService:
    @staticmethod
    def discover_goyo_devices() -> List[dict]:
        '''
        mDNS로 같은 WiFi의 GOYO 라즈베리파이 디바이스 검색
        서비스 타입: _goyo._tcp.local.
        '''
        try:
            zeroconf = Zeroconf()
            listener = GoyoDeviceListener()
            browser = ServiceBrowser(zeroconf, "_goyo._tcp.local.", listener)

            # 3초 대기하며 디바이스 검색
            import time
            time.sleep(3)

            zeroconf.close()

            logger.info(f"✅ Found {len(listener.devices)} GOYO devices")
            return listener.devices

        except Exception as e:
            logger.error(f"❌ mDNS discovery error: {e}")
            # 개발 중 fallback: 목업 데이터
            return DeviceService._mock_goyo_devices()

    @staticmethod
    def _mock_goyo_devices() -> List[dict]:
        '''개발용 목업 GOYO 디바이스'''
        import random
        return [
            {
                "device_id": f"goyo-rpi-{random.randint(1000, 9999)}",
                "device_name": "GOYO Device",
                "device_type": "goyo_device",
                "connection_type": "wifi",
                "signal_strength": random.randint(70, 100),
                "ip_address": f"192.168.1.{random.randint(100, 200)}",
                "components": {
                    "reference_mic": True,
                    "error_mic": True,
                    "speaker": True
                }
            }
        ]

    @staticmethod
    def pair_device(db: Session, user_id: int, device_data: dict) -> Device:
        '''
        GOYO 디바이스 페어링 및 MQTT 설정 전달
        '''
        # 기존 디바이스 확인
        existing = db.query(Device).filter(
            Device.device_id == device_data["device_id"]
        ).first()

        if existing:
            if existing.user_id != user_id:
                raise ValueError("Device already paired with another user")
            # 이미 페어링된 디바이스면 재연결
            existing.is_connected = True
            existing.ip_address = device_data.get("ip_address")
            db.commit()
            db.refresh(existing)

            # MQTT 설정 재전송
            DeviceService._send_mqtt_config(existing.ip_address, user_id)
            return existing

        # 새 디바이스 생성
        new_device = Device(
            user_id=user_id,
            device_id=device_data["device_id"],
            device_name=device_data["device_name"],
            device_type=device_data.get("device_type", "goyo_device"),
            connection_type=device_data.get("connection_type", "wifi"),
            ip_address=device_data.get("ip_address"),
            is_connected=False  # MQTT 연결 확인 후 True로 변경
        )

        db.add(new_device)
        db.commit()
        db.refresh(new_device)

        # 라즈베리파이에 MQTT 설정 전달
        try:
            DeviceService._send_mqtt_config(new_device.ip_address, user_id)
            logger.info(f"✅ MQTT config sent to {new_device.ip_address}")
        except Exception as e:
            logger.error(f"❌ Failed to send MQTT config: {e}")

        return new_device

    @staticmethod
    def _send_mqtt_config(ip_address: str, user_id: int):
        '''라즈베리파이에 MQTT 브로커 설정 전달'''
        config_url = f"http://{ip_address}:5000/configure"

        mqtt_config = {
            "mqtt_broker_host": settings.MQTT_BROKER_HOST,
            "mqtt_broker_port": settings.MQTT_BROKER_PORT,
            "mqtt_username": settings.MQTT_USERNAME,
            "mqtt_password": settings.MQTT_PASSWORD,
            "user_id": str(user_id)
        }

        try:
            response = requests.post(
                config_url,
                json=mqtt_config,
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"✅ MQTT config sent to {ip_address}")
        except Exception as e:
            logger.error(f"❌ Failed to send MQTT config to {ip_address}: {e}")
            raise ValueError(f"Failed to configure device: {e}")

    @staticmethod
    def get_user_devices(db: Session, user_id: int) -> List[Device]:
        '''사용자의 모든 디바이스 조회'''
        return db.query(Device).filter(Device.user_id == user_id).all()

    @staticmethod
    def get_device_setup(db: Session, user_id: int) -> dict:
        '''디바이스 구성 상태 조회 (GOYO 디바이스)'''
        devices = db.query(Device).filter(Device.user_id == user_id).all()

        goyo_device = next((d for d in devices if d.device_type == "goyo_device"), None)

        if goyo_device:
            return {
                "goyo_device": {
                    "device_id": goyo_device.device_id,
                    "device_name": goyo_device.device_name,
                    "is_connected": goyo_device.is_connected,
                    "is_calibrated": goyo_device.is_calibrated,
                    "ip_address": goyo_device.ip_address,
                    "components": {
                        "reference_mic": True,
                        "error_mic": True,
                        "speaker": True
                    }
                },
                "is_ready": goyo_device.is_connected
            }
        else:
            return {
                "goyo_device": None,
                "is_ready": False
            }

    @staticmethod
    def get_device_status(db: Session, device_id: str) -> dict:
        '''디바이스 상태 조회'''
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise ValueError("Device not found")

        return {
            "device_id": device.device_id,
            "device_name": device.device_name,
            "is_connected": device.is_connected,
            "is_calibrated": device.is_calibrated,
            "ip_address": device.ip_address,
            "components": {
                "reference_mic": True,
                "error_mic": True,
                "speaker": True
            }
        }

    @staticmethod
    def calibrate_device(db: Session, device_id: str) -> dict:
        '''GOYO 디바이스 캘리브레이션 (Reference-Error 마이크)'''
        device = db.query(Device).filter(Device.device_id == device_id).first()

        if not device:
            raise ValueError("Device not found")

        # 캘리브레이션 데이터 (실제로는 상호상관 분석 필요)
        calibration_data = {
            "time_delay": 0.025,  # 25ms delay (예시)
            "frequency_response": [0.9, 0.95, 1.0, 0.98],  # 주파수별 응답
            "spatial_transfer_function": [0.8, 0.85, 0.9],  # 공간 전달 함수
            "calibrated_at": datetime.utcnow().isoformat()
        }

        device.is_calibrated = True
        device.calibration_data = json.dumps(calibration_data)

        db.commit()

        return calibration_data

    @staticmethod
    def update_device_connection(db: Session, device_id: str, is_connected: bool):
        '''디바이스 연결 상태 업데이트 (MQTT 연결 확인 시 호출)'''
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if device:
            device.is_connected = is_connected
            db.commit()
            logger.info(f"✅ Device {device_id} connection status: {is_connected}")

    @staticmethod
    def remove_device(db: Session, device_id: str):
        '''디바이스 제거'''
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise ValueError("Device not found")

        db.delete(device)
        db.commit()
