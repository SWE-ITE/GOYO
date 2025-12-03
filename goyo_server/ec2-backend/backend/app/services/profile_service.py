from sqlalchemy.orm import Session
from app.models.user import User
from typing import Optional

class ProfileService:
    @staticmethod
    def get_user_profile(db: Session, user_id: int) -> User:
        '''사용자 프로필 조회'''
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        return user
    
    @staticmethod
    def update_profile(db: Session, user_id: int, update_data: dict) -> User:
        '''프로필 업데이트'''
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        for key, value in update_data.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_anc_settings(db: Session, user_id: int) -> dict:
        '''ANC 설정 조회'''
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        return {
            "anc_enabled": user.anc_enabled
        }
    
    @staticmethod
    def toggle_anc(db: Session, user_id: int, enabled: bool) -> User:
        '''ANC ON/OFF 토글'''
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        user.anc_enabled = enabled
        db.commit()
        db.refresh(user)

        return user