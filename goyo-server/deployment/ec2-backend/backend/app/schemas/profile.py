from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ProfileResponse(BaseModel):
    id: int
    email: str
    name: str
    anc_enabled: bool
    suppression_level: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    name: Optional[str] = None

class ANCSettings(BaseModel):
    anc_enabled: bool
    suppression_level: int = 80  # 0-100

class ANCToggle(BaseModel):
    enabled: bool

class ANCSuppressionLevel(BaseModel):
    level: int  # 0-100