from enum import Enum
from typing import Optional
import uuid
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone

class StatusType(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class Resolution(SQLModel, table=True):
    __tablename__ = "resolutions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Claimant
    claimant_id: int = Field(foreign_key="users.id", index=True) # for sending notifications

    # Linked reports
    found_item_id: uuid.UUID = Field(foreign_key="items.id", index=True, ondelete="CASCADE")

    status: StatusType = Field(default=StatusType.pending, index=True)

    # Content
    claim_description: str
    rejection_reason: Optional[str] = None

    decided_at: Optional[datetime] = None
