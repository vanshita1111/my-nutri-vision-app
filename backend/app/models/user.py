"""
User ORM model.
"""

import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Date, Float, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Health profile
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    height_cm: Mapped[Optional[float]] = mapped_column(Float)
    target_weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    activity_level: Mapped[Optional[str]] = mapped_column(String(50))  # sedentary/light/moderate/active/very_active
    goal: Mapped[Optional[str]] = mapped_column(String(50))  # lose/maintain/gain

    # Auth provider
    auth_provider: Mapped[str] = mapped_column(String(20), default="email")  # email/google/apple/guest
    google_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    apple_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)

    # Gender
    gender: Mapped[Optional[str]] = mapped_column(String(10))  # male/female/other

    # Health conditions (JSON array of string keys, e.g. ["diabetes", "pcod"])
    health_conditions: Mapped[Optional[list]] = mapped_column(JSON)

    # Cycle tracking (female wellness layer)
    last_period_date: Mapped[Optional[date]] = mapped_column(Date)
    cycle_length_days: Mapped[int] = mapped_column(default=28)

    # Relationships
    meals: Mapped[list["Meal"]] = relationship("Meal", back_populates="user", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
