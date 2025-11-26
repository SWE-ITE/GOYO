from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ApplianceBase(BaseModel):
    appliance_name: str

class ApplianceCreate(ApplianceBase):
    pass

class ApplianceUpdate(BaseModel):
    appliance_name: Optional[str] = None
    is_noise_active: Optional[bool] = None

class ApplianceResponse(ApplianceBase):
    id: int
    user_id: int
    is_noise_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
