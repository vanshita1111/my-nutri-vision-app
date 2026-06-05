"""
Pydantic schemas for user auth and profile endpoints.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal, List
from datetime import date


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class SocialAuthBody(BaseModel):
    provider: Literal["google", "apple"]
    access_token: Optional[str] = None   # Google: OAuth access token
    identity_token: Optional[str] = None  # Apple: identity JWT
    full_name: Optional[str] = None       # Apple: only available on first sign-in


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    code: str
    new_password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_premium: bool
    date_of_birth: Optional[date]
    weight_kg: Optional[float]
    height_cm: Optional[float]
    target_weight_kg: Optional[float]
    activity_level: Optional[str]
    goal: Optional[str]
    gender: Optional[str]
    health_conditions: Optional[List[str]]
    auth_provider: Optional[str]
    is_guest: bool = False
    last_period_date: Optional[date]
    cycle_length_days: int

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    weight_kg: Optional[float] = Field(default=None, gt=20, lt=300)
    height_cm: Optional[float] = Field(default=None, gt=100, lt=250)
    target_weight_kg: Optional[float] = Field(default=None, gt=20, lt=300)
    activity_level: Optional[Literal["sedentary", "light", "moderate", "active", "very_active"]] = None
    goal: Optional[Literal["lose", "maintain", "gain"]] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    health_conditions: Optional[List[str]] = None
    date_of_birth: Optional[date] = None
    last_period_date: Optional[date] = None
    cycle_length_days: Optional[int] = Field(default=None, gt=18, lt=45)
