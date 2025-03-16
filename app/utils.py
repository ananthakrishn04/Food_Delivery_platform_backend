from models import *
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import uuid
import os
from typing import Optional
from jose import JWTError, jwt

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT Settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-for-development")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Helper functions
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = db.query(UserModel).filter(UserModel.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: UserModel = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def check_role(required_role: UserRole):
    def role_checker(user: UserModel = Depends(get_current_active_user)):
        if user.role != required_role and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail=f"Operation requires {required_role} role"
            )
        return user
    return role_checker

# Calculate order total
def calculate_order_total(db: Session, items):
    total = 0
    for item in items:
        menu_item = db.query(MenuItemModel).filter(MenuItemModel.id == item.item_id).first()
        if menu_item:
            total += menu_item.price * item.quantity
    return total

# Generate mock payment
def process_payment(db: Session, order_id, total_amount):
    # In a real system, this would integrate with a payment gateway
    restaurant_share = total_amount * 0.8  # 80% to restaurant
    delivery_fee = total_amount * 0.2      # 20% as delivery fee
    
    payment_id = str(uuid.uuid4())
    payment = PaymentModel(
        id=payment_id,
        order_id=order_id,
        amount=total_amount,
        restaurant_share=restaurant_share,
        delivery_fee=delivery_fee,
        status="completed"
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    return payment