from pydantic import BaseModel, Field
from typing import List, Dict, Any
from uuid import uuid4, UUID

# Pydantic models
class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1)
    quantity: int = Field(1, ge=1)

class ItemDB(ItemCreate):
    id: UUID

class ListDB(BaseModel):
    id: UUID
    name: str
    items: List[ItemDB]