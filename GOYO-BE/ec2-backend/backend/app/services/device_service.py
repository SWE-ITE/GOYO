from sqlalchemy.orm import Session
from app.models.device import Device
from typing import List, Optional
import json
import logging
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


class DeviceService:
    @staticmethod
    def pair_device(db: Session, user_id: int, device_data: dict) -> Device:
        '''
        GOYO 디바이스 페어링 (앱에서 디바이스 검색 및 MQTT 설정 완료 후 호출)
        - DB에 디바이스 등록
        - 앱이 이미 Raspberry Pi에 MQTT 설정을 전달한 상태
        '''
        
        existing = db.query(Device).filter(
            Device.device_id == device_data["device_id"]
        ).first()

        if existing:
            if existing.user_id != user_id:
                raise ValueError("Device already paired with another user")
            
            existing.is_connected = True
            existing.ip_address = device_data.get("ip_address")
            db.commit()
            db.refresh(existing)
            logger.info(f"Device {existing.device_id} re-paired")
            return existing

        
        new_device = Device(
            user_id=user_id,
            device_id=device_data["device_id"],
            device_name=device_data["device_name"],
            device_type=device_data.get("device_type", "goyo_device"),
            connection_type=device_data.get("connection_type", "wifi"),
            ip_address=device_data.get("ip_address"),
            is_connected=False
        )

        db.add(new_device)
        db.commit()
        db.refresh(new_device)
        logger.info(f"Device {new_device.device_id} paired successfully")

        return new_device

    @staticmethod
    def get_user_devices(db: Session, user_id: int) -> List[Device]:
        '''사용자의 모든 디바이스 조회'''
        return db.query(Device).filter(Device.user_id == user_id).all()

    @staticmethod
    def get_device_setup(db: Session, user_id: int) -> dict:
        '''디바이스 구성 상태 조회'''
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
        '''GOYO 디바이스 캘리브레이션'''
        device = db.query(Device).filter(Device.device_id == device_id).first()

        if not device:
            raise ValueError("Device not found")

        
        calibration_data = {
            "time_delay": 0.025,  
            "frequency_response": [0.9, 0.95, 1.0, 0.98],  
            "spatial_transfer_function": [0.8, 0.85, 0.9],  
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
            logger.info(f"Device {device_id} connection status: {is_connected}")

    @staticmethod
    def remove_device(db: Session, device_id: str):
        '''디바이스 제거'''
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise ValueError("Device not found")

        db.delete(device)
        db.commit()
