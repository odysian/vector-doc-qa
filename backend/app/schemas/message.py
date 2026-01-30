from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MessageSource(BaseModel):
    """Schema for a single source chunk"""

    chunk_id: int
    content: str
    chunk_index: int
    similarity: float

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    """Base message schema"""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class MessageCreate(MessageBase):
    """Schema for creating a message"""

    document_id: int
    user_id: int
    sources: Optional[List[dict]] = None


class MessageResponse(MessageBase):
    """Schema for message response"""

    id: int
    document_id: int
    user_id: int
    sources: Optional[List[dict]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Schema for list of messages"""

    messages: List[MessageResponse]
    total: int
