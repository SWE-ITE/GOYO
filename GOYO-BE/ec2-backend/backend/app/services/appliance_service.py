from sqlalchemy.orm import Session
from app.models.appliance import Appliance
from app.schemas.appliance import ApplianceCreate, ApplianceUpdate
from typing import List
import logging

logger = logging.getLogger(__name__)


class ApplianceService:
    @staticmethod
    def create_appliance(db: Session, user_id: int, appliance_data: ApplianceCreate) -> Appliance:
        '''가전 생성'''
        new_appliance = Appliance(
            user_id=user_id,
            appliance_name=appliance_data.appliance_name,
            is_noise_active=False
        )

        db.add(new_appliance)
        db.commit()
        db.refresh(new_appliance)
        logger.info(f"Appliance {new_appliance.appliance_name} created for user {user_id}")

        return new_appliance

    @staticmethod
    def get_user_appliances(db: Session, user_id: int) -> List[Appliance]:
        '''사용자의 모든 가전 조회'''
        return db.query(Appliance).filter(Appliance.user_id == user_id).all()

    @staticmethod
    def get_active_appliances(db: Session, user_id: int) -> List[Appliance]:
        '''현재 소음 발생 중인 가전 조회'''
        return db.query(Appliance).filter(
            Appliance.user_id == user_id,
            Appliance.is_noise_active == True
        ).all()

    @staticmethod
    def update_appliance(db: Session, appliance_id: int, user_id: int, update_data: ApplianceUpdate) -> Appliance:
        '''가전 정보 업데이트'''
        appliance = db.query(Appliance).filter(
            Appliance.id == appliance_id,
            Appliance.user_id == user_id
        ).first()

        if not appliance:
            raise ValueError("Appliance not found")

        
        if update_data.appliance_name is not None:
            appliance.appliance_name = update_data.appliance_name
        if update_data.is_noise_active is not None:
            appliance.is_noise_active = update_data.is_noise_active

        db.commit()
        db.refresh(appliance)
        logger.info(f"Appliance {appliance_id} updated")

        return appliance

    @staticmethod
    def delete_appliance(db: Session, appliance_id: int, user_id: int):
        '''가전 삭제'''
        appliance = db.query(Appliance).filter(
            Appliance.id == appliance_id,
            Appliance.user_id == user_id
        ).first()

        if not appliance:
            raise ValueError("Appliance not found")

        db.delete(appliance)
        db.commit()
        logger.info(f"Appliance {appliance_id} deleted")

    @staticmethod
    def update_noise_status(db: Session, user_id: int, is_noise_active: bool) -> List[Appliance]:
        '''
        사용자의 모든 가전 소음 상태 업데이트
        (라즈베리파이 VAD에서 호출)
        '''
        appliances = db.query(Appliance).filter(Appliance.user_id == user_id).all()

        if not appliances:
            raise ValueError(f"No appliances found for user {user_id}")

        
        for appliance in appliances:
            appliance.is_noise_active = is_noise_active

        db.commit()
        logger.info(f"Updated noise status for user {user_id}: is_noise_active={is_noise_active}")

        return appliances
