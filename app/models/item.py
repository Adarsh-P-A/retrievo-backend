from enum import Enum
from typing import Optional
import uuid
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone

class ItemType(str, Enum):
    lost = "lost"
    found = "found"

class VisibilityType(str, Enum):
    public = "public"
    boys = "boys"
    girls = "girls"

class HiddenReasonType(str, Enum):
    auto_report_threshold = "auto_report_threshold"
    admin_moderation = "admin_moderation"

class Item(SQLModel, table=True):
    __tablename__ = "items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Reporter info
    user_id: int = Field(foreign_key="users.id")

    # Item fields
    title: str
    category: str
    description: str
    location: str
    type: ItemType = Field(index=True)
    date: datetime
    image: str
    visibility: VisibilityType = Field(default=VisibilityType.public, index=True)

    # Moderation
    is_hidden: bool = Field(default=False)
    hidden_reason: Optional[HiddenReasonType] = Field(default=None)
