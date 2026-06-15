"""Pydantic schemas for auth and users."""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: dict


class UserSettings(BaseModel):
    aiProvider: str = "openai"
    dailyTarget: int = 30
    targetBand: float = 7.5
    examDate: str | None = None
    focusModules: list[str] = Field(default_factory=lambda: ["Academic", "Writing", "Speaking"])


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    settings: UserSettings
