# Add these imports at the top of your file
from fastapi import WebSocket, Depends
from typing import Dict, List
from models import UserRole, UserModel, Session, get_db


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, List[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, order_id: str = None):
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        
        if order_id:
            if order_id not in self.active_connections[user_id]:
                self.active_connections[user_id][order_id] = []
            self.active_connections[user_id][order_id].append(websocket)
        else:
            if "all" not in self.active_connections[user_id]:
                self.active_connections[user_id]["all"] = []
            self.active_connections[user_id]["all"].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str, order_id: str = None):
        if user_id in self.active_connections:
            if order_id and order_id in self.active_connections[user_id]:
                self.active_connections[user_id][order_id].remove(websocket)
                if not self.active_connections[user_id][order_id]:
                    del self.active_connections[user_id][order_id]
            elif "all" in self.active_connections[user_id]:
                self.active_connections[user_id]["all"].remove(websocket)
                if not self.active_connections[user_id]["all"]:
                    del self.active_connections[user_id]["all"]
            
            if not self.active_connections[user_id]:    
                del self.active_connections[user_id]

    async def send_order_update(self, user_id: str, order_id: str, message: dict):
        if user_id in self.active_connections:
            if order_id in self.active_connections[user_id]:
                for connection in self.active_connections[user_id][order_id]:
                    await connection.send_json(message)
            
            if "all" in self.active_connections[user_id]:
                for connection in self.active_connections[user_id]["all"]:
                    await connection.send_json(message)

    async def broadcast_to_restaurant(self, restaurant_id: str, message: dict):
        if restaurant_id in self.active_connections:
            if "all" in self.active_connections[restaurant_id]:
                for connection in self.active_connections[restaurant_id]["all"]:
                    await connection.send_json(message)

    async def broadcast_to_delivery_agents(self, message: dict):
        for user_id, connections in self.active_connections.items():
            user = await get_user_by_id(user_id)
            if user and user.role == UserRole.DELIVERY_AGENT:
                if "all" in connections:
                    for connection in connections["all"]:
                        await connection.send_json(message)

# Add this helper function to get user by ID
async def get_user_by_id(user_id: str, db: Session = Depends(get_db)):
    return db.query(UserModel).filter(UserModel.id == user_id).first()