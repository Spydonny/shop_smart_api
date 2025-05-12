from pydantic import BaseModel, Field
from typing import List, Dict, Any
from uuid import uuid4, UUID

# Модели для работы с базой данных

class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1)
    quantity: int = Field(1, ge=1)

class ItemDB(ItemCreate):
    id: UUID
    price: float
    is_bought: bool

    class Config:
        allow_mutation = True

class ItemUpdate(BaseModel):
    title: str
    quantity: int
    is_bought: bool 

class ListCreate(BaseModel):
    name: str = Field(default="New List")

class ListDB(ListCreate):
    id: UUID
    items: List[ItemDB]
    updated_at: float 

# Модель для генерации текста

class GenerationRequest(BaseModel):
    prompt: str

class GenerationResponse(BaseModel):
    generated_text: str