from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.device import (
    DeviceDiscover, 
    DevicePair, 
    DeviceResponse, 
    DeviceCalibrate
)
from app.services.device_service import DeviceService
from app.utils.dependencies import get_current_user_id  # 변경됨!
from typing import List

router = APIRouter(prefix="/api/devices", tags=["Device Management"])

@router.post("/discover/usb", response_model=List[DeviceDiscover])
def discover_usb_microphones(user_id: int = Depends(get_current_user_id)):  # 인증 추가
    '''
    USB 마이크 검색 (노트북에 연결된 마이크)
    '''
    try:
        devices = DeviceService.discover_usb_microphones()
        return devices
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/discover/wifi", response_model=List[DeviceDiscover])
def discover_wifi_speakers(user_id: int = Depends(get_current_user_id)):  # 인증 추가
    '''
    Wi-Fi 스피커 검색
    '''
    try:
        speakers = DeviceService.discover_wifi_speakers()
        return speakers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/pair", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def pair_device(
    device_data: DevicePair,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)  # 이제 실제 JWT에서 추출
):
    '''
    디바이스 페어링
    '''
    try:
        device = DeviceService.pair_device(db, user_id, device_data.dict())
        return device
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/microphone/{device_id}/role")
def assign_microphone_role(
    device_id: str,
    role: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)  # 인증 추가
):
    '''
    마이크 역할 지정
    '''
    try:
        device = DeviceService.assign_microphone_role(db, device_id, role)
        return {
            "message": "Microphone role assigned",
            "device_id": device.device_id,
            "device_type": device.device_type
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=List[DeviceResponse])
def get_devices(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)  # 인증 추가
):
    '''
    사용자의 모든 디바이스 조회
    '''
    devices = DeviceService.get_user_devices(db, user_id)
    return devices

@router.get("/setup")
def get_microphone_setup(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)  # 인증 추가
):
    '''
    현재 마이크/스피커 구성 상태 조회
    '''
    setup = DeviceService.get_microphone_setup(db, user_id)
    return setup

@router.get("/status/{device_id}")
def get_device_status(
    device_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)  # 인증 추가
):
    '''
    특정 디바이스 상태 조회
    '''
    try:
        status = DeviceService.get_device_status(db, device_id)
        return status
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.post("/calibrate/dual-mic")
def calibrate_dual_microphones(
    source_device_id: str,
    reference_device_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)  # 인증 추가
):
    '''
    두 마이크 간 캘리브레이션
    '''
    try:
        calibration_data = DeviceService.calibrate_dual_microphones(
            db, 
            source_device_id, 
            reference_device_id
        )
        return {
            "message": "Dual microphone calibration successful",
            "calibration_data": calibration_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(
    device_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)  # 인증 추가
):
    '''
    디바이스 제거
    '''
    try:
        DeviceService.remove_device(db, device_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )