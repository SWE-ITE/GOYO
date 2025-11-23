from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.redis_client import redis_client
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
        '''ANC 설정 조회 (DB + Redis)'''
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Redis에서 실시간 상태 확인
        redis_status = redis_client.get_user_session(user_id)
        
        return {
            "anc_enabled": user.anc_enabled,
            "suppression_level": user.suppression_level,
            "redis_status": redis_status
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
        
        # Redis에 실시간 상태 저장
        redis_client.set_user_session(user_id, {
            "anc_enabled": enabled,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        })
        
        return user
    
    @staticmethod
    def set_suppression_level(db: Session, user_id: int, level: int) -> User:
        '''억제 강도 설정 (0-100)'''
        if not 0 <= level <= 100:
            raise ValueError("Suppression level must be between 0 and 100")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        user.suppression_level = level
        db.commit()
        db.refresh(user)
        
        # Redis 업데이트
        redis_client.set_user_session(user_id, {
            "anc_enabled": user.anc_enabled,
            "suppression_level": level,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        })
        
        return user