import uuid
from pydantic import BaseModel, Field


class ResolutionCreateRequest(BaseModel):
    found_item_id: uuid.UUID
    claim_description: str = Field(min_length=20, max_length=280)

class ResolutionRejectRequest(BaseModel):
    rejection_reason: str = Field(min_length=20, max_length=280)