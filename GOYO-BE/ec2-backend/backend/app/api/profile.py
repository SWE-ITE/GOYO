from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.profile import (
    ProfileResponse,
    ProfileUpdate
)
from app.services.profile_service import ProfileService
from app.utils.dependencies import get_current_user, get_current_user_id
from app.models.user import User

router = APIRouter(prefix="/api/profile", tags=["Profile"])

@router.get("/", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    '''
    현재 사용자 프로필 조회
    '''
    return current_user

@router.put("/", response_model=ProfileResponse)
def update_profile(
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    '''
    프로필 업데이트 (이름 변경)
    '''
    try:
        user = ProfileService.update_profile(
            db,
            user_id,
            profile_data.dict(exclude_unset=True)
        )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )