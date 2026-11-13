"""Pydantic schemas for auth and users."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


FocusModule = Literal["Academic", "General", "Writing", "Speaking", "Reading", "Listening"]
AiProviderName = Literal["openai", "anthropic", "ollama"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordChange(BaseModel):
    currentPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: dict


class UserSettings(BaseModel):
    aiProvider: AiProviderName = "openai"
    dailyTarget: int = Field(default=30, ge=5, le=200)
    targetBand: float = Field(default=7.5, ge=4, le=9)
    examDate: str | None = None
    focusModules: list[FocusModule] = Field(
        default_factory=lambda: ["Academic", "Writing", "Speaking"],
        max_length=6,
    )

    @field_validator("examDate")
    @classmethod
    def _exam_date(cls, value: str | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        text = str(value).strip()
        datetime.strptime(text, "%Y-%m-%d")
        return text

    @field_validator("focusModules")
    @classmethod
    def _unique_modules(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    settings: UserSettings
