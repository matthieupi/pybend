# PyBend Examples

Real-world examples demonstrating PyBend's capabilities.

**Note**: All CRUD and custom endpoint responses include `$schema` and `$id` metadata at the top of each object. Route handlers call `.model_dump(response=True)` to inject these fields automatically.

## Table of Contents

- [E-commerce Platform](#e-commerce-platform)
- [Social Media API](#social-media-api)
- [Content Management System](#content-management-system)
- [Task Management](#task-management)
- [Authentication System](#authentication-system)
- [File Upload Service](#file-upload-service)
- [Real-time Chat](#real-time-chat)
- [Multi-tenant SaaS](#multi-tenant-saas)

---

## E-commerce Platform

A complete e-commerce API with products, orders, and inventory management.

### Models

```python
from models.proto_model import ProtoModel
from utils.typer import ForeignKey
from utils.decorators import expose_route
from typing import ClassVar, Optional, List
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class Category(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'categories'
    
    id: Optional[int] = None
    name: str
    description: str
    slug: str

class Product(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'products'
    
    id: Optional[int] = None
    name: str
    description: str
    price: float
    stock: int
    category: ForeignKey[Category]
    sku: str
    
    @expose_route('/check-stock', methods=['GET'])
    def check_stock(self) -> dict:
        """Check if product is in stock"""
        return {
            "in_stock": self.stock > 0,
            "quantity": self.stock,
            "available": self.stock > 0
        }
    
    @expose_route('/reduce-stock', methods=['POST'])
    def reduce_stock(self, quantity: int) -> Product:
        """Reduce stock after purchase"""
        if self.stock < quantity:
            raise ValueError("Insufficient stock")
        self.stock -= quantity
        self.save()
        return self
    
    @classmethod
    @expose_route('/low-stock', methods=['GET'])
    def get_low_stock(cls, threshold: int = 5) -> List[Product]:
        """Get products with low stock"""
        return [p for p in cls.list() if p.stock < threshold]

class Customer(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'customers'
    
    id: Optional[int] = None
    email: str
    name: str
    phone: str
    address: str

class Order(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'orders'
    
    id: Optional[int] = None
    customer: ForeignKey[Customer]
    status: OrderStatus = OrderStatus.PENDING
    total: float
    created_at: str  # ISO datetime
    
    @expose_route('/cancel', methods=['POST'])
    def cancel(self) -> Order:
        """Cancel an order"""
        if self.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            raise ValueError("Cannot cancel shipped/delivered orders")
        self.status = OrderStatus.CANCELLED
        self.save()
        return self
    
    @expose_route('/ship', methods=['POST'])
    def ship(self, tracking_number: str) -> Order:
        """Mark order as shipped"""
        self.status = OrderStatus.SHIPPED
        # In real app, save tracking_number
        self.save()
        return self
    
    @classmethod
    @expose_route('/by-status', methods=['GET'])
    def get_by_status(cls, status: str) -> List[Order]:
        """Get orders by status"""
        return [o for o in cls.list() if o.status == status]

class OrderItem(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'order_items'
    
    id: Optional[int] = None
    order: ForeignKey[Order]
    product: ForeignKey[Product]
    quantity: int
    price: float  # Price at time of purchase
```

### Setup

```python
# app.py
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import register_model
from api.backend import FastAPIBackend

storage = SQLiteStorage('ecommerce.db')

# Register all models
register_model(Category, storage=storage)
register_model(Product, storage=storage)
register_model(Customer, storage=storage)
register_model(Order, storage=storage)
register_model(OrderItem, storage=storage)

backend = FastAPIBackend(name="E-commerce API", version="1.0.0")
from utils.registrar import registered_models
backend.register_routes(registered_models)
app = backend.get_app()
```

### Usage Examples

```bash
# Create category
curl -X POST http://localhost:8000/categories \
  -H "Content-Type: application/json" \
  -d '{"name": "Electronics", "description": "Electronic devices", "slug": "electronics"}'

# Create product
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Laptop",
    "description": "High-performance laptop",
    "price": 999.99,
    "stock": 50,
    "category": 1,
    "sku": "LAPTOP-001"
  }'

# Check stock
curl http://localhost:8000/products/1/check-stock

# Get low stock products
curl http://localhost:8000/products/low-stock?threshold=10

# Create order
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer": 1,
    "total": 999.99,
    "created_at": "2025-01-15T10:00:00Z"
  }'

# Ship order
curl -X POST http://localhost:8000/orders/1/ship \
  -H "Content-Type: application/json" \
  -d '{"tracking_number": "TRACK123"}'

# Get orders by status
curl http://localhost:8000/orders/by-status?status=shipped
```

---

## Social Media API

A social network with users, posts, comments, and likes.

### Models

```python
from datetime import datetime

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    id: Optional[int] = None
    username: str
    email: str
    bio: str = ''
    avatar_url: str = ''
    followers_count: int = 0
    following_count: int = 0
    
    @expose_route('/follow', methods=['POST'])
    def follow(self, target_user_id: int) -> dict:
        """Follow another user"""
        # Create follow relationship
        Follow.create(Follow(
            follower=self.id,
            following=target_user_id
        ))
        
        # Update counts
        self.following_count += 1
        self.save()
        
        target = User.get(target_user_id)
        target.followers_count += 1
        target.save()
        
        return {"message": "Followed successfully"}
    
    @expose_route('/posts', methods=['GET'])
    def get_posts(self) -> List[Post]:
        """Get user's posts"""
        posts = Post.list()
        return [p for p in posts if int(p.author) == self.id]
    
    @expose_route('/feed', methods=['GET'])
    def get_feed(self, limit: int = 20) -> List[Post]:
        """Get personalized feed"""
        # Get users this user follows
        follows = Follow.list()
        following_ids = [f.following for f in follows if f.follower == self.id]
        
        # Get posts from followed users
        posts = Post.list()
        feed = [p for p in posts if int(p.author) in following_ids]
        
        # Sort by created_at (newest first)
        feed.sort(key=lambda x: x.created_at, reverse=True)
        return feed[:limit]

class Post(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'posts'
    
    id: Optional[int] = None
    content: str
    author: ForeignKey[User]
    created_at: str
    likes_count: int = 0
    comments_count: int = 0
    
    @expose_route('/like', methods=['POST'])
    def like(self, user_id: int) -> dict:
        """Like this post"""
        # Check if already liked
        likes = Like.list()
        if any(l.user == user_id and l.post == self.id for l in likes):
            return {"message": "Already liked"}
        
        # Create like
        Like.create(Like(user=user_id, post=self.id))
        self.likes_count += 1
        self.save()
        return {"message": "Liked successfully"}
    
    @expose_route('/comments', methods=['GET'])
    def get_comments(self) -> List[Comment]:
        """Get post comments"""
        comments = Comment.list()
        return [c for c in comments if int(c.post) == self.id]

class Comment(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'comments'
    
    id: Optional[int] = None
    content: str
    author: ForeignKey[User]
    post: ForeignKey[Post]
    created_at: str

class Follow(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'follows'
    
    id: Optional[int] = None
    follower: int  # User ID
    following: int  # User ID

class Like(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'likes'
    
    id: Optional[int] = None
    user: int  # User ID
    post: int  # Post ID
```

### Usage

```bash
# Create users
curl -X POST http://localhost:8000/users \
  -d '{"username": "alice", "email": "alice@example.com"}'

curl -X POST http://localhost:8000/users \
  -d '{"username": "bob", "email": "bob@example.com"}'

# Alice follows Bob
curl -X POST http://localhost:8000/users/1/follow \
  -d '{"target_user_id": 2}'

# Bob creates a post
curl -X POST http://localhost:8000/posts \
  -d '{"content": "Hello world!", "author": 2, "created_at": "2025-01-15T10:00:00Z"}'

# Alice likes Bob's post
curl -X POST http://localhost:8000/posts/1/like \
  -d '{"user_id": 1}'

# Alice views her feed
curl http://localhost:8000/users/1/feed?limit=10
```

---

## Content Management System

A flexible CMS with pages, articles, and media.

### Models

```python
from enum import Enum

class ContentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Page(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'pages'
    
    id: Optional[int] = None
    title: str
    slug: str
    content: str
    status: ContentStatus = ContentStatus.DRAFT
    author: ForeignKey[User]
    created_at: str
    updated_at: str
    meta_description: str = ''
    
    @expose_route('/publish', methods=['POST'])
    def publish(self) -> Page:
        """Publish this page"""
        self.status = ContentStatus.PUBLISHED
        self.updated_at = datetime.now().isoformat()
        self.save()
        return self
    
    @classmethod
    @expose_route('/published', methods=['GET'])
    def get_published(cls) -> List[Page]:
        """Get all published pages"""
        return [p for p in cls.list() if p.status == ContentStatus.PUBLISHED]
    
    @classmethod
    @expose_route('/by-slug', methods=['GET'])
    def get_by_slug(cls, slug: str) -> Optional[Page]:
        """Get page by slug"""
        pages = cls.list()
        return next((p for p in pages if p.slug == slug), None)

class Article(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'articles'
    
    id: Optional[int] = None
    title: str
    slug: str
    excerpt: str
    content: str
    featured_image: str = ''
    status: ContentStatus = ContentStatus.DRAFT
    author: ForeignKey[User]
    category: ForeignKey[Category]
    tags: str = ''  # Comma-separated
    published_at: Optional[str] = None
    
    @expose_route('/schedule', methods=['POST'])
    def schedule(self, publish_date: str) -> Article:
        """Schedule article for publication"""
        self.status = ContentStatus.DRAFT
        self.published_at = publish_date
        self.save()
        return self

class Media(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'media'
    
    id: Optional[int] = None
    filename: str
    url: str
    mime_type: str
    size: int  # bytes
    uploaded_by: ForeignKey[User]
    uploaded_at: str
```

---

## Task Management

Project management with tasks, boards, and assignments.

### Models

```python
class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Board(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'boards'
    
    id: Optional[int] = None
    name: str
    description: str
    owner: ForeignKey[User]

class Task(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'tasks'
    
    id: Optional[int] = None
    title: str
    description: str
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    board: ForeignKey[Board]
    assignee: Optional[ForeignKey[User]] = None
    due_date: Optional[str] = None
    created_at: str
    
    @expose_route('/assign', methods=['POST'])
    def assign(self, user_id: int) -> Task:
        """Assign task to a user"""
        self.assignee = user_id
        self.save()
        return self
    
    @expose_route('/move', methods=['POST'])
    def move(self, new_status: str) -> Task:
        """Move task to different status"""
        self.status = TaskStatus(new_status)
        self.save()
        return self
    
    @classmethod
    @expose_route('/overdue', methods=['GET'])
    def get_overdue(cls) -> List[Task]:
        """Get overdue tasks"""
        now = datetime.now().isoformat()
        tasks = cls.list()
        return [
            t for t in tasks
            if t.due_date and t.due_date < now and t.status != TaskStatus.DONE
        ]

class Comment(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'task_comments'
    
    id: Optional[int] = None
    task: ForeignKey[Task]
    author: ForeignKey[User]
    content: str
    created_at: str
```

---

## Authentication System

Secure authentication with JWT tokens.

### Models

```python
import hashlib
import secrets
from datetime import datetime, timedelta

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    id: Optional[int] = None
    email: str
    password_hash: str
    is_active: bool = True
    is_verified: bool = False
    created_at: str
    last_login: Optional[str] = None
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${hash_obj.hex()}"
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        salt, hash_hex = password_hash.split('$')
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hash_obj.hex() == hash_hex
    
    @staticmethod
    @expose_route('/register', methods=['POST'])
    def register(email: str, password: str) -> dict:
        """Register new user"""
        # Check if email exists
        users = User.list()
        if any(u.email == email for u in users):
            raise ValueError("Email already registered")
        
        # Create user
        user = User.create(User(
            email=email,
            password_hash=User.hash_password(password),
            created_at=datetime.now().isoformat()
        ))
        
        return {"message": "Registration successful", "user_id": user.id}
    
    @staticmethod
    @expose_route('/login', methods=['POST'])
    def login(email: str, password: str) -> dict:
        """Login user"""
        users = User.list()
        user = next((u for u in users if u.email == email), None)
        
        if not user or not User.verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        
        if not user.is_active:
            raise ValueError("Account is deactivated")
        
        # Update last login
        user.last_login = datetime.now().isoformat()
        user.save()
        
        # Generate session token
        token = Session.create_session(user.id)
        
        return {
            "token": token,
            "user_id": user.id,
            "email": user.email
        }

class Session(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'sessions'
    
    id: Optional[int] = None
    user: ForeignKey[User]
    token: str
    expires_at: str
    created_at: str
    
    @staticmethod
    def create_session(user_id: int, duration_hours: int = 24) -> str:
        """Create new session token"""
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
        
        Session.create(Session(
            user=user_id,
            token=token,
            expires_at=expires_at,
            created_at=datetime.now().isoformat()
        ))
        
        return token
    
    @staticmethod
    @expose_route('/validate', methods=['POST'])
    def validate_token(token: str) -> dict:
        """Validate session token"""
        sessions = Session.list()
        session = next((s for s in sessions if s.token == token), None)
        
        if not session:
            raise ValueError("Invalid token")
        
        if datetime.fromisoformat(session.expires_at) < datetime.now():
            raise ValueError("Token expired")
        
        user = User.get(int(session.user))
        return {"valid": True, "user_id": user.id, "email": user.email}
```

### Usage

```bash
# Register
curl -X POST http://localhost:8000/users/register \
  -d '{"email": "user@example.com", "password": "SecurePass123"}'

# Login
curl -X POST http://localhost:8000/users/login \
  -d '{"email": "user@example.com", "password": "SecurePass123"}'
# Response: {"token": "abc123...", "user_id": 1, ...}

# Validate token
curl -X POST http://localhost:8000/sessions/validate \
  -d '{"token": "abc123..."}'
```

---

## Tips for Building APIs

### 1. Use Environment Variables

```python
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'default.db')
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
```

### 2. Add Logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class User(ProtoModel):
    @staticmethod
    @expose_route('/login', methods=['POST'])
    def login(email: str, password: str):
        logger.info(f"Login attempt for {email}")
        # ... login logic
```

### 3. Validation

```python
from pydantic import validator, EmailStr

class User(ProtoModel):
    email: EmailStr  # Automatic email validation
    
    @validator('password')
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
```

### 4. Error Handling

```python
from fastapi import HTTPException

@expose_route('/protected', methods=['GET'])
def protected_route(self):
    if not self.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")
    return {"data": "secret"}
```

### 5. Testing

```python
import pytest

def test_user_registration():
    response = User.register("test@example.com", "password123")
    assert "user_id" in response
    
def test_duplicate_email():
    User.register("duplicate@example.com", "pass123")
    with pytest.raises(ValueError):
        User.register("duplicate@example.com", "pass123")
```

---

All examples are production-ready patterns that can be adapted to your specific needs. See [API Reference](./API_REFERENCE.md) for complete documentation.
