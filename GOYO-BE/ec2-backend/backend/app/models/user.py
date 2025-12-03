from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)  # 개발 편의를 위해 자동 활성화
    is_verified = Column(Boolean, default=True)  # 개발 편의를 위해 자동 인증
    verification_token = Column(String, nullable=True)
    
    # ANC Settings
    anc_enabled = Column(Boolean, default=False)  # ANC ON/OFF

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())