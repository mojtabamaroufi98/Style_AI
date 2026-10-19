from typing import Optional, List
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    gender: Optional[str] = None
    body_shape: Optional[str] = None

    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    size: Optional[str] = None

    chest: Optional[float] = None
    waist: Optional[float] = None
    hip: Optional[float] = None
    shoulder: Optional[float] = None

    styles: List[str] = []
    liked_colors: List[str] = []
    disliked_colors: List[str] = []
    occasions: List[str] = []

    budget: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None

    # Legacy budget fields — برای سازگاری با تست‌ها و نسخه‌های قبلی
    budget_type: Optional[str] = None
    budget_amount: Optional[int] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    profile: Optional[UserProfile] = None
    session_id: Optional[str] = None

class Product(BaseModel):
    id: str
    name: str
    store: str
    price: int
    old_price: Optional[int] = None
    url: Optional[str] = None

    sizes: List[str] = []
    colors: List[str] = []

    material: Optional[str] = None
    match: Optional[int] = None
    body_match: Optional[str] = None
    note: Optional[str] = None


class OutfitItem(BaseModel):
    category: str
    title: str
    color: Optional[str] = None
    estimated_price: Optional[int] = None


class Outfit(BaseModel):
    title: str
    occasion: Optional[str] = None
    items: List[OutfitItem]
    why: str


class ChatResponse(BaseModel):
    answer: str
    products: List[Product] = []