from pydantic import BaseModel, Field, AnyHttpUrl
from uuid import uuid4, UUID
from datetime import datetime
from typing import Optional

class RegisterRequest(BaseModel):
    name: str = Field(min_length = 1,)
    url: AnyHttpUrl
    health_path: str = "/health"

class ServiceInformation(RegisterRequest):
    service_id: UUID = Field(default_factory=uuid4)
    service_health: bool = True
    failed_attempts: int = 0
    last_health_verification: Optional[datetime] = None

class ServiceDiscoveryResponse(RegisterRequest):
    service_id: UUID
    service_health: bool = True