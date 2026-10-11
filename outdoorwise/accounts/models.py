from datetime import datetime
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AccountCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=256)


class UsernameAvailability(BaseModel):
    username: str
    available: bool


class UserPublic(BaseModel):
    user_id: str
    username: str
    created_at: AwareDatetime


class AccountRecord(UserPublic):
    normalized_username: str
    password_hash: str
    updated_at: AwareDatetime


class SessionRecord(BaseModel):
    token_hash: str
    user_id: str
    created_at: datetime
    expires_at: datetime
