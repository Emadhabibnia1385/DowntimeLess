from typing import Optional

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    name: str
    username: Optional[str]
    role: str
    has_password: bool
    tg_username: Optional[str]


class StartResult(BaseModel):
    challenge_id: int
    deep_link: str
    poll_secret: str
    expires_in: int


class PollRequest(BaseModel):
    challenge_id: int
    poll_secret: str


class PollResult(BaseModel):
    status: str
    user: Optional[UserOut] = None


class WebAppRequest(BaseModel):
    init_data: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordRequest(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=64)
    password: str = Field(max_length=256)
    current_password: Optional[str] = Field(default=None, max_length=256)
