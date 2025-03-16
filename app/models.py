from sqlalchemy import create_engine, Column, String, Float, Boolean, ForeignKey, DateTime, Integer, Enum as SQLAEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import List
import os


# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/food_delivery")
# Handle special case for Render.com's DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    RESTAURANT = "restaurant"
    CUSTOMER = "customer"
    DELIVERY_AGENT = "delivery_agent"

class OrderStatus(str, Enum):
    PLACED = "placed"
    ACCEPTED = "accepted"
    ASSIGNED = "assigned_to_delivery"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"

# Database Models
class UserModel(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    role = Column(SQLAEnum(UserRole))
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)
    
    # Relationships
    restaurant_menu_items = relationship("MenuItemModel", back_populates="restaurant")
    customer_orders = relationship("OrderModel", foreign_keys="OrderModel.customer_id", back_populates="customer")
    restaurant_orders = relationship("OrderModel", foreign_keys="OrderModel.restaurant_id", back_populates="restaurant")
    delivery_orders = relationship("OrderModel", foreign_keys="OrderModel.delivery_agent_id", back_populates="delivery_agent")

class MenuItemModel(Base):
    __tablename__ = "menu_items"
    
    id = Column(String, primary_key=True, index=True)
    restaurant_id = Column(String, ForeignKey("users.id"))
    name = Column(String)
    description = Column(String)
    price = Column(Float)
    is_available = Column(Boolean, default=True)
    
    # Relationships
    restaurant = relationship("UserModel", back_populates="restaurant_menu_items")

class OrderModel(Base):
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("users.id"))
    restaurant_id = Column(String, ForeignKey("users.id"))
    delivery_agent_id = Column(String, ForeignKey("users.id"), nullable=True)
    items = Column(String)  # Store as JSON string
    total_amount = Column(Float)
    status = Column(SQLAEnum(OrderStatus))
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    
    # Relationships
    customer = relationship("UserModel", foreign_keys=[customer_id], back_populates="customer_orders")
    restaurant = relationship("UserModel", foreign_keys=[restaurant_id], back_populates="restaurant_orders")
    delivery_agent = relationship("UserModel", foreign_keys=[delivery_agent_id], back_populates="delivery_orders")
    payment = relationship("PaymentModel", back_populates="order", uselist=False)

class PaymentModel(Base):
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), unique=True)
    amount = Column(Float)
    restaurant_share = Column(Float)
    delivery_fee = Column(Float)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.now())
    
    # Relationships
    order = relationship("OrderModel", back_populates="payment")

# Create all tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Models for API
class UserBase(BaseModel):
    username: str
    email: str
    role: UserRole

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
    role: UserRole | None = None

class MenuItemBase(BaseModel):
    name: str
    description: str
    price: float
    is_available: bool = True

class MenuItem(MenuItemBase):
    id: str
    restaurant_id: str
    
    class Config:
        orm_mode = True

class OrderItemDict(BaseModel):
    item_id: str
    quantity: int

class OrderCreate(BaseModel):
    restaurant_id: str
    items: List[OrderItemDict]

class OrderUpdate(BaseModel):
    status: OrderStatus
    delivery_agent_id: str | None = None

class Order(BaseModel):
    id: str
    customer_id: str
    restaurant_id: str
    items: List[OrderItemDict]
    total_amount: float
    status: OrderStatus
    delivery_agent_id: str | None = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class Payment(BaseModel):
    id: str
    order_id: str
    amount: float
    restaurant_share: float
    delivery_fee: float
    status: str
    created_at: datetime
    
    class Config:
        orm_mode = True