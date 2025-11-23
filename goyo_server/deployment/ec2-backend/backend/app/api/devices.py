from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.device import (
    DevicePair,
    DeviceResponse,
    DeviceCalibrate,
    DeviceStatus
)
from app.services.device_service import DeviceService
from app.utils.dependencies import get_current_user_id
from typing import List

router = APIRouter(prefix="/api/devices", tags=["Device Management"])

@router.post("/pair", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def pair_device(
    device_data: DevicePair,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    GOYO 디바이스 페어링 (앱에서 디바이스 검색 및 MQTT 설정 완료 후 호출)
    - DB에 디바이스 등록
    - 라즈베리파이가 MQTT 연결 시 is_connected = True
    '''
    try:
        device = DeviceService.pair_device(db, user_id, device_data.dict())
        return device
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=List[DeviceResponse])
def get_devices(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    사용자의 모든 디바이스 조회
    '''
    devices = DeviceService.get_user_devices(db, user_id)
    return devices

@router.get("/setup")
def get_device_setup(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    현재 GOYO 디바이스 구성 상태 조회
    '''
    setup = DeviceService.get_device_setup(db, user_id)
    return setup

@router.get("/status/{device_id}", response_model=DeviceStatus)
def get_device_status(
    device_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
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

@router.post("/calibrate/{device_id}")
def calibrate_device(
    device_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    GOYO 디바이스 캘리브레이션 (Reference-Error 마이크)
    '''
    try:
        calibration_data = DeviceService.calibrate_device(db, device_id)
        return {
            "message": "Device calibration successful",
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
    user_id: int = Depends(get_current_user_id)
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
