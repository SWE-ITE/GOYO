from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, unique=True, nullable=False)
    device_type = Column(String, nullable=False)  
    device_name = Column(String, nullable=False)
    is_connected = Column(Boolean, default=False)
    connection_type = Column(String, default="wifi")  
    ip_address = Column(String, nullable=True)  

    
    is_calibrated = Column(Boolean, default=False)
    calibration_data = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="devices")