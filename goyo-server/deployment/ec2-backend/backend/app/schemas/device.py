from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict

class DeviceBase(BaseModel):
    device_name: str
    device_type: str = "goyo_device"  # GOYO ANC Device (Reference + Error 마이크 + 스피커)
    connection_type: str = "wifi"

class DeviceDiscover(BaseModel):
    device_id: str
    device_name: str
    device_type: str = "goyo_device"
    connection_type: str = "wifi"
    signal_strength: Optional[int] = None
    ip_address: str
    components: Dict[str, bool] = {
        "reference_mic": True,
        "error_mic": True,
        "speaker": True
    }

class DevicePair(BaseModel):
    device_id: str
    device_name: str
    device_type: str = "goyo_device"
    connection_type: str = "wifi"
    ip_address: str

class DeviceCalibrate(BaseModel):
    device_id: str
    calibration_type: str = "dual_mic"  # Reference-Error 마이크 캘리브레이션

class DeviceResponse(BaseModel):
    id: int
    user_id: int
    device_id: str
    device_name: str
    device_type: str
    is_connected: bool
    connection_type: str
    ip_address: Optional[str] = None
    is_calibrated: bool
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceStatus(BaseModel):
    device_id: str
    device_name: str
    is_connected: bool
    is_calibrated: bool
    ip_address: Optional[str] = None
    components: Dict[str, bool] = {
        "reference_mic": True,
        "error_mic": True,
        "speaker": True
    }
    last_seen: Optional[datetime] = None