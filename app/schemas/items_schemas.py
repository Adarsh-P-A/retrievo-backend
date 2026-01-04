from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ItemUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=30)
    location: Optional[str] = Field(None, min_length=3, max_length=30)
    description: Optional[str] = Field(None, min_length=20, max_length=280)
    category: Optional[Literal["electronics", "clothing", "bags", "keys-wallets", "documents", "others"]] = None
    visibility: Optional[Literal["public", "boys", "girls"]] = None
    date: Optional[datetime] = None

    @field_validator("title", "location", "description", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v
    
class ReportCreateSchema(BaseModel):
    reason: Literal['spam', 'inappropriate', 'harassment', 'fake', 'other']