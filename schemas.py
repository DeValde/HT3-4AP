from pydantic import BaseModel, HttpUrl, EmailStr
from datetime import datetime
from typing import Optional

class LinkBase(BaseModel):
    original_url: HttpUrl

class LinkCreate(LinkBase):
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None

class LinkUpdate(BaseModel):
    original_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None

class LinkStats(BaseModel):
    original_url: HttpUrl
    created_at: datetime
    last_accessed: Optional[datetime] = None
    click_count: int

    class Config:
        orm_mode = True

class LinkResponse(BaseModel):
    short_code: str
    original_url: HttpUrl
    expires_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None