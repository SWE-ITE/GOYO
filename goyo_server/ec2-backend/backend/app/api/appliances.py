from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.appliance import (
    ApplianceCreate,
    ApplianceUpdate,
    ApplianceResponse
)
from app.services.appliance_service import ApplianceService
from app.utils.dependencies import get_current_user_id
from typing import List

router = APIRouter(prefix="/api/appliances", tags=["Appliance Management"])

@router.post("/", response_model=ApplianceResponse, status_code=status.HTTP_201_CREATED)
def create_appliance(
    appliance_data: ApplianceCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    가전 추가
    '''
    appliance = ApplianceService.create_appliance(db, user_id, appliance_data)
    return appliance

@router.get("/", response_model=List[ApplianceResponse])
def get_appliances(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    사용자의 모든 가전 조회
    '''
    appliances = ApplianceService.get_user_appliances(db, user_id)
    return appliances

@router.get("/active", response_model=List[ApplianceResponse])
def get_active_appliances(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    현재 소음 발생 중인 가전 조회
    '''
    active_appliances = ApplianceService.get_active_appliances(db, user_id)
    return active_appliances

@router.put("/{appliance_id}", response_model=ApplianceResponse)
def update_appliance(
    appliance_id: int,
    update_data: ApplianceUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    가전 정보 업데이트 (소음 상태 포함)
    '''
    try:
        appliance = ApplianceService.update_appliance(db, appliance_id, user_id, update_data)
        return appliance
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.delete("/{appliance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appliance(
    appliance_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    가전 삭제
    '''
    try:
        ApplianceService.delete_appliance(db, appliance_id, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
