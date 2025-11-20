from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class DeviceBase(BaseModel):
    device_name: str
    device_type: str  # "microphone_source", "microphone_reference", "speaker"
    connection_type: str  # "usb" or "wifi"

class DeviceDiscover(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    connection_type: str
    signal_strength: Optional[int] = None
    is_usb: bool = False

class DevicePair(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    connection_type: str

class DeviceCalibrate(BaseModel):
    device_id: str
    calibration_type: str = "environment"  # environment, latency, dual_mic

class DeviceResponse(BaseModel):
    id: int
    user_id: int
    device_id: str
    device_name: str
    device_type: str
    is_connected: bool
    connection_type: str
    is_calibrated: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class DeviceStatus(BaseModel):
    device_id: str
    is_connected: bool
    is_calibrated: bool
    last_seen: Optional[datetime] = None
    audio_level: Optional[float] = None  # 현재 오디오 레벨