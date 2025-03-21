﻿# Food Delivery API

A robust food delivery platform API built with FastAPI, featuring a comprehensive system for restaurants, customers, and delivery agents with real-time order status updates and notifications.

## Tech Stack

- **Backend Framework**: FastAPI (Python 3.11)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Authentication**: JWT (JSON Web Tokens)
- **API Documentation**: Swagger UI / OpenAPI
- **Password Hashing**: Bcrypt

## Features

### 1. Multi-Role Authentication System
- Support for multiple user roles:
  - Customers
  - Restaurant Owners
  - Delivery Agents
  - Administrators
- Secure JWT-based authentication
- Role-based access control (RBAC)

### 2. Restaurant Management
- Menu item creation and management
- Real-time availability updates
- Restaurant profile management
- Order tracking and management

### 3. Order System
- Real-time order status tracking
- Multiple order states (placed, accepted, assigned, picked up, delivered)
- Order history for all users
- Detailed order information including items and quantities

### 4. Payment System
- Payment tracking
- Restaurant share calculation
- Delivery fee management
- Payment status monitoring

### 5. Delivery Management
- Delivery agent assignment
- Real-time delivery status updates
- Delivery history tracking

## Installation

### Prerequisites
- Python 3.11 or higher
- PostgreSQL
- pip (Python package manager)

### Local Setup

1. Clone the repository
```bash
git clone <repository-url>
cd <repository-name>
```

2. Create and activate a virtual environment
```bash
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On Unix or MacOS
source venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
Create a `.env` file in the root directory with the following variables:
```env
DATABASE_URL=postgresql://<username>:<password>@localhost/food_delivery
SECRET_KEY=your-secret-key
```

5. Initialize the database
```bash
# Create the database
createdb food_delivery

# Run migrations (if using Alembic)
alembic upgrade head
```

6. Run the application
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once the application is running, you can access:
- Swagger UI documentation at `http://localhost:8000/docs`
- ReDoc documentation at `http://localhost:8000/redoc`


## API Endpoints

### Authentication
- `POST /auth/login` - Get access token / Login user
- `POST /auth/register` - Register new user


### Restaurants
- `GET /restaurants` - List all restaurants
- `GET /restaurants/{id}/menu` - Get restaurant menu
- `GET /menu-items/` - Get all menu items (optional query param: restaurant_id)
- `POST /menu-items/` - Create a new menu item (restaurant only)
- `PUT /menu-items/{item_id}` - Update a menu item (restaurant only)
- `DELETE /menu-items/{item_id}` - Delete a menu item (restaurant only)

### Orders
- `POST /orders` - Create new order
- `GET /orders/` - Get user's orders
- `PUT /orders/{id}` - Update order status
- `GET /orders/{id}` - Get order details

### Payments
- `POST /payments` - Create payment

## Deployment - Render.com
```bash
https://food-delivery-platform-backend.onrender.com
```

## License

This project is licensed under the MIT License - see the LICENSE file for details
