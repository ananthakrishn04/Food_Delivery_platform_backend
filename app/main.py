from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.consumers import ConnectionManager

from typing import List
import uuid
import json
import asyncio
from app.models import *
from app.utils import *

# Initialize FastAPI app
app = FastAPI(title="Food Delivery System API")

# Create an instance of the connection manager
manager = ConnectionManager()


# Routes
@app.post("/register", response_model=User)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(UserModel).filter(UserModel.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user.password)
    
    db_user = UserModel(
        id=user_id,
        username=user.username,
        email=user.email,
        role=user.role,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Restaurant Menu Management
@app.post("/menu-items/", response_model=MenuItem)
async def create_menu_item(
    menu_item: MenuItemBase,
    current_user: UserModel = Depends(check_role(UserRole.RESTAURANT)),
    db: Session = Depends(get_db)
):
    item_id = str(uuid.uuid4())
    
    db_menu_item = MenuItemModel(
        id=item_id,
        restaurant_id=current_user.id,
        name=menu_item.name,
        description=menu_item.description,
        price=menu_item.price,
        is_available=menu_item.is_available
    )
    
    db.add(db_menu_item)
    db.commit()
    db.refresh(db_menu_item)
    
    return db_menu_item

@app.get("/menu-items/", response_model=List[MenuItem])
async def get_menu_items(restaurant_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(MenuItemModel)
    if restaurant_id:
        query = query.filter(MenuItemModel.restaurant_id == restaurant_id)
    return query.all()

@app.put("/menu-items/{item_id}", response_model=MenuItem)
async def update_menu_item(
    item_id: str,
    menu_item: MenuItemBase,
    current_user: UserModel = Depends(check_role(UserRole.RESTAURANT)),
    db: Session = Depends(get_db)
):
    db_menu_item = db.query(MenuItemModel).filter(MenuItemModel.id == item_id).first()
    if not db_menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    # Ensure restaurant can only update their own menu items
    if db_menu_item.restaurant_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to update this menu item")
    
    db_menu_item.name = menu_item.name
    db_menu_item.description = menu_item.description
    db_menu_item.price = menu_item.price
    db_menu_item.is_available = menu_item.is_available
    
    db.commit()
    db.refresh(db_menu_item)
    
    return db_menu_item

@app.delete("/menu-items/{item_id}", status_code=204)
async def delete_menu_item(
    item_id: str,
    current_user: UserModel = Depends(check_role(UserRole.RESTAURANT)),
    db: Session = Depends(get_db)
):
    db_menu_item = db.query(MenuItemModel).filter(MenuItemModel.id == item_id).first()
    if not db_menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    # Ensure restaurant can only delete their own menu items
    if db_menu_item.restaurant_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to delete this menu item")
    
    db.delete(db_menu_item)
    db.commit()
    
    return None

    
# Order Management (continued)
@app.post("/orders/", response_model=Order)
async def create_order(
    order: OrderCreate,
    current_user: UserModel = Depends(check_role(UserRole.CUSTOMER)),
    db: Session = Depends(get_db)
):
    # Validate restaurant exists
    restaurant = db.query(UserModel).filter(
        UserModel.id == order.restaurant_id,
        UserModel.role == UserRole.RESTAURANT
    ).first()
    
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    # Validate items exist
    for item in order.items:
        menu_item = db.query(MenuItemModel).filter(MenuItemModel.id == item.item_id).first()
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item {item.item_id} not found")
        if menu_item.restaurant_id != order.restaurant_id:
            raise HTTPException(status_code=400, detail=f"Menu item {item.item_id} does not belong to the selected restaurant")
    
    # Calculate total
    total_amount = calculate_order_total(db, order.items)
    
    order_id = str(uuid.uuid4())
    now = datetime.now()
    
    # Convert items to JSON for storage
    items_json = json.dumps([item.dict() for item in order.items])
    
    # Create order
    db_order = OrderModel(
        id=order_id,
        customer_id=current_user.id,
        restaurant_id=order.restaurant_id,
        items=items_json,
        total_amount=total_amount,
        status=OrderStatus.PLACED,
        created_at=now,
        updated_at=now
    )
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Process payment
    process_payment(db, order_id, total_amount)
    
    await manager.broadcast_to_restaurant(db_order.restaurant_id, {
        "type": "new_order",
        "order_id": db_order.id,
        "customer_id": db_order.customer_id,
        "total_amount": db_order.total_amount,
        "created_at": db_order.created_at.isoformat()
    })
    
    return Order(
        id=db_order.id,
        customer_id=db_order.customer_id,
        restaurant_id=db_order.restaurant_id,
        items=order.items,
        total_amount=db_order.total_amount,
        status=db_order.status,
        delivery_agent_id=db_order.delivery_agent_id,
        created_at=db_order.created_at,
        updated_at=db_order.updated_at
    )

@app.get("/orders/", response_model=List[Order])
async def get_orders(
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(OrderModel)
    
    if current_user.role == UserRole.ADMIN:
        orders = query.all()
    elif current_user.role == UserRole.CUSTOMER:
        orders = query.filter(OrderModel.customer_id == current_user.id).all()
    elif current_user.role == UserRole.RESTAURANT:
        orders = query.filter(OrderModel.restaurant_id == current_user.id).all()
    elif current_user.role == UserRole.DELIVERY_AGENT:
        orders = query.filter(OrderModel.delivery_agent_id == current_user.id).all()
    else:
        orders = []
    
    # Convert JSON items back to list of dictionaries
    result = []
    for order in orders:
        items = json.loads(order.items)
        items_obj = [OrderItemDict(**item) for item in items]
        
        result.append(Order(
            id=order.id,
            customer_id=order.customer_id,
            restaurant_id=order.restaurant_id,
            items=items_obj,
            total_amount=order.total_amount,
            status=order.status,
            delivery_agent_id=order.delivery_agent_id,
            created_at=order.created_at,
            updated_at=order.updated_at
        ))
    
    return result

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    role = current_user.role
    user_id = current_user.id
    
    # Ensure proper authorization
    if (role == UserRole.CUSTOMER and order.customer_id != user_id) or \
        (role == UserRole.RESTAURANT and order.restaurant_id != user_id) or \
        (role == UserRole.DELIVERY_AGENT and order.delivery_agent_id != user_id and order.status != OrderStatus.ASSIGNED):
        if role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Not authorized to view this order")
    
    # Convert JSON items back to list of dictionaries
    items = json.loads(order.items)
    items_obj = [OrderItemDict(**item) for item in items]
    
    return Order(
        id=order.id,
        customer_id=order.customer_id,
        restaurant_id=order.restaurant_id,
        items=items_obj,
        total_amount=order.total_amount,
        status=order.status,
        delivery_agent_id=order.delivery_agent_id,
        created_at=order.created_at,
        updated_at=order.updated_at
    )

@app.put("/orders/{order_id}", response_model=Order)
async def update_order_status(
    order_id: str,
    order_update: OrderUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    role = current_user.role
    user_id = current_user.id
    
    # Ensure proper authorization for status updates
    authorized = False
    
    if role == UserRole.ADMIN:
        authorized = True
    elif role == UserRole.RESTAURANT and order.restaurant_id == user_id:
        if order_update.status in [OrderStatus.ACCEPTED, OrderStatus.ASSIGNED]:
            authorized = True
    elif role == UserRole.DELIVERY_AGENT and (order.delivery_agent_id == user_id or order.status == OrderStatus.ASSIGNED):
        if order_update.status in [OrderStatus.PICKED_UP, OrderStatus.DELIVERED]:
            authorized = True
            # If taking the order, assign to this delivery agent
            if order_update.status == OrderStatus.PICKED_UP and not order.delivery_agent_id:
                order_update.delivery_agent_id = user_id
    
    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized to update this order status")
    
    # Status transition validation
    valid_transitions = {
        OrderStatus.PLACED: [OrderStatus.ACCEPTED],
        OrderStatus.ACCEPTED: [OrderStatus.ASSIGNED],
        OrderStatus.ASSIGNED: [OrderStatus.PICKED_UP],
        OrderStatus.PICKED_UP: [OrderStatus.DELIVERED],
        OrderStatus.DELIVERED: []
    }
    
    if order_update.status not in valid_transitions[order.status]:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status transition from {order.status} to {order_update.status}"
        )
    
    # Update order
    order.status = order_update.status
    if order_update.delivery_agent_id:
        order.delivery_agent_id = order_update.delivery_agent_id
    order.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    
    # Send real-time update to customer
    update_message = {
        "type": "order_update",
        "order_id": order.id,
        "status": order.status,
        "updated_at": order.updated_at.isoformat()
    }
    
    # Send to customer
    await manager.send_order_update(order.customer_id, order.id, update_message)
    
    # Send to restaurant
    await manager.send_order_update(order.restaurant_id, order.id, update_message)
    
    # Send to delivery agent if assigned
    if order.delivery_agent_id:
        await manager.send_order_update(order.delivery_agent_id, order.id, update_message)
    
    # Broadcast to all delivery agents if status changed to "ASSIGNED"
    if order.status == OrderStatus.ASSIGNED and not order.delivery_agent_id:
        await manager.broadcast_to_delivery_agents({
            "type": "order_available",
            "order_id": order.id,
            "restaurant_id": order.restaurant_id,
            "created_at": order.created_at.isoformat()
        })
    
    # Convert JSON items back to list of dictionaries
    items = json.loads(order.items)
    items_obj = [OrderItemDict(**item) for item in items]
    
    return Order(
        id=order.id,
        customer_id=order.customer_id,
        restaurant_id=order.restaurant_id,
        items=items_obj,
        total_amount=order.total_amount,
        status=order.status,
        delivery_agent_id=order.delivery_agent_id,
        created_at=order.created_at,
        updated_at=order.updated_at
    )

# Payment Routes
@app.post("/payments/", response_model=Payment)
async def create_payment(
    order_id: str, 
    current_user: UserModel = Depends(check_role(UserRole.CUSTOMER)),
    db: Session = Depends(get_db)
):
    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify customer owns this order
    if order.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to process payment for this order")
    
    # Check if payment already exists
    existing_payment = db.query(PaymentModel).filter(PaymentModel.order_id == order_id).first()
    if existing_payment:
        return existing_payment
    
    # Process payment
    payment = process_payment(db, order_id, order.total_amount)
    return payment

# Add websocket endpoints
@app.websocket("/ws/orders/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str = None):
    if token:
        try:
            # Verify the token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            
            db = SessionLocal()
            try:
                user = db.query(UserModel).filter(UserModel.username == username).first()
                if not user or user.id != user_id:
                    await websocket.close(code=1008)
                    return
            finally:
                db.close()
        except jwt.PyJWTError:
            await websocket.close(code=1008)
            return
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Keep the connection alive
            data = await websocket.receive_text()
            # You can handle client messages here if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

@app.websocket("/ws/orders/{user_id}/{order_id}")
async def websocket_specific_order(websocket: WebSocket, user_id: str, order_id: str, token: str = None):
    if token:
        try:
            # Verify the token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            
            db = SessionLocal()
            try:
                user = db.query(UserModel).filter(UserModel.username == username).first()
                if not user or user.id != user_id:
                    await websocket.close(code=1008)
                    return
                
                # Check if order exists and belongs to user
                order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
                if not order or (user.role == UserRole.CUSTOMER and order.customer_id != user_id):
                    await websocket.close(code=1008)
                    return
            finally:
                db.close()
        except jwt.PyJWTError:
            await websocket.close(code=1008)
            return
    
    await manager.connect(websocket, user_id, order_id)
    
    try:
        while True:
            # Keep the connection alive
            data = await websocket.receive_text()
            # You can handle client messages here if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, order_id)

 
# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

# Create admin user on startup
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        # Create admin user if it doesn't exist
        admin_user = db.query(UserModel).filter(UserModel.username == "admin").first()
        if not admin_user:
            admin_id = str(uuid.uuid4())
            hashed_password = get_password_hash("admin123")  # Change in production!
            
            admin_user = UserModel(
                id=admin_id,
                username="admin",
                email="admin@fooddelivery.com",
                role=UserRole.ADMIN,
                hashed_password=hashed_password
            )
            
            db.add(admin_user)
            db.commit()
            print("Admin user created")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)