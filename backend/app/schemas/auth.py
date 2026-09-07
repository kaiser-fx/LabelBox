import re
from datetime import datetime
from pydantic import BaseModel, field_validator

NIC_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@nic\.in$", re.IGNORECASE)


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_nic_domain(cls, v: str) -> str:
        clean = v.strip().lower()
        if not NIC_EMAIL_REGEX.match(clean):
            raise ValueError("Only valid @nic.in email addresses are allowed.")
        return clean


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer_id: str
    name: str
    email: str
    badge_number: str | None = None
    jurisdiction: str | None = None


class OfficerResponse(BaseModel):
    id: str
    name: str
    email: str
    badge_number: str | None = None
    jurisdiction: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
