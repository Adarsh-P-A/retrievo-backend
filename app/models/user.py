from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    public_id: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # User fields
    name: str
    image: str
    email: str
    phone: Optional[str] = Field(default=None)
    hostel: Optional[str] = Field(default=None)  # Possible values: boys, girls

    role: str = Field(default="user")  # Possible roles: user, admin

    # Moderation
    warning_count: int = Field(default=0)
    
    is_banned: bool = Field(default=False, index=True)
    ban_reason: Optional[str] = Field(default=None)
    ban_until: Optional[datetime] = Field(default=None)
