from sqlalchemy.orm import Session
from app.models.device import Device
from app.utils.audio_device import audio_manager
from typing import List, Optional
import random
import json
from datetime import datetime

class DeviceService:
    @staticmethod
    def discover_usb_microphones() -> List[dict]:
        '''USB 마이크 검색'''
        usb_mics = audio_manager.list_usb_microphones()
        return usb_mics
    
    @staticmethod
    def discover_wifi_speakers() -> List[dict]:
        '''Wi-Fi 스피커 검색 (시뮬레이션)'''
        # 실제로는 mDNS/UPnP 스캔 필요
        mock_speakers = [
            {
                "device_id": f"SPK_WIFI_{random.randint(1000, 9999)}",
                "device_name": "GOYO Smart Speaker",
                "device_type": "speaker",
                "connection_type": "wifi",
                "signal_strength": random.randint(70, 100),
                "ip_address": f"192.168.1.{random.randint(100, 200)}"
            }
        ]
        return mock_speakers
    
    @staticmethod
    def pair_device(db: Session, user_id: int, device_data: dict) -> Device:
        '''디바이스 페어링'''
        existing = db.query(Device).filter(
            Device.device_id == device_data["device_id"]
        ).first()
        
        if existing:
            if existing.user_id != user_id:
                raise ValueError("Device already paired with another user")
            return existing
        
        new_device = Device(
            user_id=user_id,
            device_id=device_data["device_id"],
            device_name=device_data["device_name"],
            device_type=device_data["device_type"],
            connection_type=device_data["connection_type"],
            is_connected=True
        )
        
        db.add(new_device)
        db.commit()
        db.refresh(new_device)

        return new_device
    
    @staticmethod
    def assign_microphone_role(db: Session, device_id: str, role: str) -> Device:
        '''마이크 역할 지정 (source or reference)'''
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise ValueError("Device not found")
        
        if role not in ["microphone_source", "microphone_reference"]:
            raise ValueError("Invalid role. Must be 'microphone_source' or 'microphone_reference'")
        
        device.device_type = role
        db.commit()
        db.refresh(device)
        
        return device
    
    @staticmethod
    def get_user_devices(db: Session, user_id: int) -> List[Device]:
        '''사용자의 모든 디바이스 조회'''
        return db.query(Device).filter(Device.user_id == user_id).all()
    
    @staticmethod
    def get_microphone_setup(db: Session, user_id: int) -> dict:
        '''마이크 구성 상태 조회'''
        devices = db.query(Device).filter(Device.user_id == user_id).all()
        
        source_mic = next((d for d in devices if d.device_type == "microphone_source"), None)
        ref_mic = next((d for d in devices if d.device_type == "microphone_reference"), None)
        speaker = next((d for d in devices if d.device_type == "speaker"), None)
        
        return {
            "source_microphone": source_mic.device_name if source_mic else None,
            "reference_microphone": ref_mic.device_name if ref_mic else None,
            "speaker": speaker.device_name if speaker else None,
            "is_ready": all([source_mic, ref_mic, speaker])
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
            "device_type": device.device_type,
            "is_connected": device.is_connected,
            "is_calibrated": device.is_calibrated
        }
    
    @staticmethod
    def calibrate_dual_microphones(db: Session, source_id: str, ref_id: str) -> dict:
        '''두 마이크 간 시간 지연 및 응답 캘리브레이션'''
        source = db.query(Device).filter(Device.device_id == source_id).first()
        ref = db.query(Device).filter(Device.device_id == ref_id).first()
        
        if not source or not ref:
            raise ValueError("One or both microphones not found")
        
        # 캘리브레이션 데이터 (실제로는 상호상관 분석 필요)
        calibration_data = {
            "time_delay": 0.025,  # 25ms delay (예시)
            "frequency_response": [0.9, 0.95, 1.0, 0.98],  # 주파수별 응답
            "spatial_transfer_function": [0.8, 0.85, 0.9],  # 공간 전달 함수
            "calibrated_at": datetime.utcnow().isoformat()
        }
        
        source.is_calibrated = True
        source.calibration_data = json.dumps(calibration_data)
        ref.is_calibrated = True
        ref.calibration_data = json.dumps(calibration_data)
        
        db.commit()
        
        return calibration_data
    
    @staticmethod
    def remove_device(db: Session, device_id: str):
        '''디바이스 제거'''
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise ValueError("Device not found")

        db.delete(device)
        db.commit()