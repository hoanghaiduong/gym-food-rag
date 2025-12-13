from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProductBase(BaseModel):
    name: str
    price: int
    image_url: Optional[str] = None
    description: Optional[str] = None
    category: str = "supplements" 
    affiliate_link: Optional[str] = None
    batch_id: Optional[str] = None
    audit_id: Optional[str] = None

class ProductCreate(ProductBase):
    stock: int = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    stock: Optional[int] = None

class ProductResponse(ProductBase):
    id: int
    stock: int
    created_at: datetime
    class Config:
        from_attributes = True

class OrderRequest(BaseModel):
    user_id: int
    product_id: int
    quantity: int = 1
    shipping_address: Optional[str] = None
    note: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    total_price: int
    status: str
    created_at: datetime
    class Config:
        from_attributes = True