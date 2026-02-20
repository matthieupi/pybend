# Getting Started with PyBend

This guide will walk you through building your first API with PyBend in under 10 minutes.

## Prerequisites

- Python 3.8+
- pip or poetry for package management
- Basic understanding of REST APIs
- Familiarity with Python type hints (helpful but not required)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/pybend.git
cd pybend
```

### 2. Install Dependencies

```bash
pip install pydantic fastapi uvicorn
```

**Optional dependencies**:
```bash
# For Flask backend
pip install flask flasgger asgiref

# For development
pip install pytest black mypy
```

### 3. Verify Installation

```bash
python -c "from models.proto_model import ProtoModel; print('✓ PyBend installed')"
```

## Your First API (5 minutes)

Let's build a simple blog API with users and posts.

### Step 1: Define Your Models

Create `models/blog_models.py`:

```python
from models.proto_model import ProtoModel
from utils.typer import Ref
from typing import ClassVar, Optional, List

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    id: Optional[int] = None
    username: str
    email: str
    bio: Optional[str] = ''

class Post(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'posts'
    
    id: Optional[int] = None
    title: str
    content: str
    published: bool = False
    author: Ref[User]  # Foreign key to User
```

That's it! No manual SQL, no migrations scripts, no route definitions needed.

### Step 2: Register Models and Start Server

Create `app.py`:

```python
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import register_model
from api.backend import FastAPIBackend
import config

# Import your models
from models.blog_models import User, Post

# Create storage backend
storage = SQLiteStorage('blog.db')

# Register models (automatic table creation + migration)
register_model(User, storage=storage)
register_model(Post, storage=storage)

# Create API backend
backend = FastAPIBackend(
    name="Blog API",
    version="1.0.0",
    description="A simple blog API built with PyBend",
    port=8000
)

# Register routes (automatic CRUD endpoints)
from utils.registrar import registered_models
backend.register_routes(registered_models)

# Get the app
app = backend.get_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
```

### Step 3: Run Your API

```bash
python app.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 4: Test Your API

**View automatic documentation**:
- Open http://localhost:8000/docs in your browser
- You'll see interactive Swagger documentation

**Create a user** (using curl):
```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "bio": "Software developer"
  }'
```

Response:
```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "bio": "Software developer"
}
```

**List all users**:
```bash
curl http://localhost:8000/users
```

**Create a post**:
```bash
curl -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "Hello PyBend!",
    "author": 1
  }'
```

**Update a post**:
```bash
curl -X PUT http://localhost:8000/posts/1 \
  -H "Content-Type: application/json" \
  -d '{
    "published": true
  }'
```

**Delete a user**:
```bash
curl -X DELETE http://localhost:8000/users/1
```

## What Just Happened?

PyBend automatically created:

### For User Model:
- ✅ `GET /users` - List all users
- ✅ `POST /users` - Create a user
- ✅ `GET /users/{id}` - Get user by ID
- ✅ `PUT /users/{id}` - Update user
- ✅ `DELETE /users/{id}` - Delete user
- ✅ `GET /User` - Get JSON schema

### For Post Model:
- ✅ `GET /posts` - List all posts
- ✅ `POST /posts` - Create a post
- ✅ `GET /posts/{id}` - Get post by ID
- ✅ `PUT /posts/{id}` - Update post
- ✅ `DELETE /posts/{id}` - Delete post
- ✅ `GET /Post` - Get JSON schema

### Database:
- ✅ SQLite database `blog.db` created
- ✅ Tables `users` and `posts` created
- ✅ Foreign key relationship configured
- ✅ Auto-incrementing IDs

### Validation:
- ✅ All inputs validated via Pydantic
- ✅ Type checking enforced
- ✅ Required fields enforced
- ✅ JSON serialization automatic

## Adding Custom Logic

Let's add custom endpoints to our models.

### Step 1: Add Custom Methods

Edit `models/blog_models.py`:

```python
from utils.decorators import expose_route

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    username: str
    email: str
    bio: Optional[str] = ''
    
    @staticmethod
    @expose_route('/login', methods=['POST'])
    def login(username: str, password: str) -> User:
        """
        Custom login endpoint
        Creates: POST /users/login
        """
        users = User.list()
        user = next((u for u in users if u.username == username), None)
        if user:
            # In production, check password hash
            return user
        raise ValueError("Invalid credentials")
    
    @expose_route('/posts', methods=['GET'])
    def get_posts(self) -> List[Post]:
        """
        Get all posts by this user
        Creates: GET /users/{id}/posts
        """
        all_posts = Post.list()
        return [p for p in all_posts if int(p.author) == self.id]

class Post(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'posts'
    
    title: str
    content: str
    published: bool = False
    author: Ref[User]
    
    @expose_route('/publish', methods=['POST'])
    def publish(self) -> Post:
        """
        Publish this post
        Creates: POST /posts/{id}/publish
        """
        self.published = True
        self.save()  # Built-in save method
        return self
    
    @classmethod
    @expose_route('/published', methods=['GET'])
    def get_published(cls) -> List[Post]:
        """
        Get all published posts
        Creates: GET /posts/published
        """
        return [p for p in cls.list() if p.published]
```

### Step 2: Restart Server

```bash
# Ctrl+C to stop, then:
python app.py
```

### Step 3: Test Custom Endpoints

**Login**:
```bash
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "secret123"
  }'
```

**Get user's posts**:
```bash
curl http://localhost:8000/users/1/posts
```

**Publish a post**:
```bash
curl -X POST http://localhost:8000/posts/1/publish
```

**Get all published posts**:
```bash
curl http://localhost:8000/posts/published
```

## Adding Validation

Use Pydantic's validation features:

```python
from pydantic import field_validator, EmailStr

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    username: str
    email: EmailStr  # Automatic email validation
    
    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v
    
    @field_validator('email')
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()
```

Now invalid data will be rejected automatically:

```bash
# This will fail (invalid email)
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "email": "not-an-email"}'

# Response: 422 Unprocessable Entity
```

## Many-to-Many Relationships

Let's add tags to posts:

### Step 1: Define Tag Model

```python
class Tag(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'tags'
    
    name: str
    color: str = '#000000'

class Post(ProtoModel):
    # ... existing fields ...
    tags: Optional[List[Tag]] = []
```

### Step 2: Generate Join Model

```python
from models.proto_model import generate_join_model

# In app.py, after registering Post and Tag:
PostTag = generate_join_model(Post, Tag)
register_model(PostTag, storage=storage)
```

This creates a `posts_tags` join table automatically.

### Step 3: Add Tags to Posts

```bash
# Create tags
curl -X POST http://localhost:8000/tags \
  -H "Content-Type: application/json" \
  -d '{"name": "python", "color": "#3776ab"}'

curl -X POST http://localhost:8000/tags \
  -H "Content-Type: application/json" \
  -d '{"name": "tutorial", "color": "#ff6b6b"}'

# Add tag to post (via join table)
curl -X POST http://localhost:8000/posts/1/tags \
  -H "Content-Type: application/json" \
  -d '{"name": "python", "color": "#3776ab"}'
```

## Switching Storage Backends

PyBend supports multiple storage backends. Let's switch to JSON files:

### Step 1: Change Storage Backend

Edit `app.py`:

```python
# Change this:
# from storage.sqlite_storage import SQLiteStorage
# storage = SQLiteStorage('blog.db')

# To this:
from storage.json_storage import JSONStorage
storage = JSONStorage(directory='data')  # Creates data/ folder
```

### Step 2: Restart Server

```bash
python app.py
```

Now your data is stored in `data/users.json` and `data/posts.json` as human-readable JSON files.

## Using Flask Instead of FastAPI

PyBend supports multiple web frameworks:

### Change Backend

Edit `app.py`:

```python
# Change this:
# from api.backend import FastAPIBackend
# backend = FastAPIBackend(...)

# To this:
from api.backend import FlaskBackend
backend = FlaskBackend(
    name="Blog API",
    version="1.0.0",
    description="Flask-powered blog API"
)
```

Everything else stays the same!

## Next Steps

Now that you have a working API, explore:

### Advanced Features
- [Custom validation](./API_REFERENCE.md#validation)
- [Middleware and hooks](./ARCHITECTURE.md#middleware-hooks)
- [Authentication](./EXAMPLES.md#authentication)
- [Pagination](./EXAMPLES.md#pagination)
- [File uploads](./EXAMPLES.md#file-uploads)

### Production Deployment
- [Deployment guide](./DEPLOYMENT.md)
- [Security best practices](./SECURITY.md)
- [Performance optimization](./PERFORMANCE.md)

### Documentation
- [Full API Reference](./API_REFERENCE.md)
- [Architecture Overview](./ARCHITECTURE.md)
- [More Examples](./EXAMPLES.md)

## Common Issues

### Import Error: "No module named 'models'"

Make sure you're running from the project root:
```bash
cd pybend
python app.py
```

### Database Locked Error

SQLite only supports one writer at a time. For concurrent writes:
```python
# Use connection pooling or switch to PostgreSQL
# Coming soon in PyBend
```

### Foreign Key Not Resolving

Foreign keys are stored as IDs. To get the full object:
```python
post = Post.get(1)
user_id = int(post.author)  # Get ID
user = User.get(user_id)    # Fetch full user
```

Or implement lazy loading:
```python
class Post(ProtoModel):
    @property
    def author_obj(self):
        return User.get(int(self.author))
```

### Port Already in Use

Change the port in `app.py`:
```python
backend = FastAPIBackend(port=8080)  # Use different port
```

## Tips and Tricks

### 1. Enable Debug Mode

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="debug"
    )
```

### 2. Generate Documentation

```bash
GENERATE_DOCS=true python app.py
# Creates docs/*.md files
```

### 3. Use Type Hints

Enable autocomplete in your IDE:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.blog_models import User

def get_user() -> User:
    return User.get(1)  # IDE knows it returns User
```

### 4. Test Your API

```python
import pytest

def test_create_user():
    user = User.create(User(username="test", email="test@example.com"))
    assert user.id is not None
    assert user.username == "test"
```

### 5. Environment Variables

```python
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'blog.db')
storage = SQLiteStorage(DATABASE_URL)
```

## Getting Help

- 📖 [Read the documentation](./README.md)
- 🐛 [Report issues](https://github.com/yourusername/pybend/issues)
- 💬 [Join discussions](https://github.com/yourusername/pybend/discussions)
- 📧 [Email support](mailto:support@pybend.dev)

## What's Next?

You now have a fully functional REST API with:
- ✅ Automatic CRUD operations
- ✅ Type-safe validation
- ✅ Foreign key relationships
- ✅ Custom business logic
- ✅ Automatic documentation
- ✅ Flexible storage backends

**Continue learning**:
- Build a more complex app in [Examples](./EXAMPLES.md)
- Understand the architecture in [Architecture Guide](./ARCHITECTURE.md)
- Deploy to production in [Deployment Guide](./DEPLOYMENT.md)
- Learn advanced patterns in [API Reference](./API_REFERENCE.md)

Happy coding with PyBend! 🚀
