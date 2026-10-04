from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class UserCreate(BaseModel):
    email: str
    password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    id: UUID
    email: str
    is_active: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
