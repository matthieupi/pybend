---

# **PyBend Documentation**

## **Table of Contents**

1. [Introduction](#introduction)
2. [Features](#features)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [API Documentation](#api-documentation)
7. [Usage Examples](#usage-examples)
8. [Extending the Application](#extending-the-application)
9. [Switching Storage Backends](#switching-storage-backends)
10. [Testing](#testing)

---

## **Introduction**

This application is a modular, extensible API built using Flask, Pydantic, and Flasgger. It allows you to define models with optional storage capabilities, automatically generate CRUD endpoints for storable models, and add custom endpoints using decorators.

---

## **Features**

- **Dynamic Model Registration**: Models can be registered with or without storage capabilities.
- **Automatic CRUD Endpoints**: For models with storage, CRUD endpoints are automatically generated.
- **Custom Endpoints**: Add custom endpoints to models using the `@expose_route` decorator.
- **Storage Backend Abstraction**: Easily switch between different storage backends (SQLite, JSON files).
- **Swagger Integration**: API documentation is automatically generated using Swagger (OpenAPI 3.x).
- **Flexible Architecture**: The codebase is organized for scalability and maintainability.

---

## **Installation**

### **Prerequisites**

- **Docker**: Ensure Docker is installed on your system.
- **Docker Compose**: Required to build and run the application using `docker-compose`.

### **Clone the Repository**

```bash
git clone https://github.com/yourusername/yourrepository.git
cd yourrepository
```

### **Directory Structure**

```
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── app
    ├── __init__.py
    ├── main.py
    ├── models
    │   ├── __init__.py
    │   ├── proto_model.py
    │   ├── storable_mixin.py
    │   ├── user_model.py
    │   └── product_model.py
    │   ├── viewable_mixin.py
    ├── storage
    │   ├── __init__.py
    │   ├── storage_interface.py
    │   ├── sqlite_storage.py
    │   └── json_storage.py
    ├── utils
    │   ├── __init__.py
    │   ├── registrar.py
    │   └── decorators.py
    ├── api
    │   ├── __init__.py
    │   └── routes.py
    └── tests
        ├── __init__.py
        ├── conftest.py
        ├── test_models.py
        └── test_api.py
```

---

## **Configuration**

### **Environment Variables**

You can configure the application using environment variables. Create a `.env` file in the root directory (if needed):

```
DATABASE_URL=sqlite:///database.db
STORAGE_BACKEND=sqlite  # Options: sqlite, json
```

### **Requirements**

The `requirements.txt` file specifies the necessary Python packages:

```
Flask==2.3.2
pydantic==2.0.3
flasgger==0.9.5
PyYAML==6.0
pytest==7.2.1
pytest-flask==1.2.0
```

---

## **Running the Application**

### **Build and Run with Docker Compose**

```bash
docker-compose up --build
```

This command builds the Docker image and starts the application on `http://localhost:5000`.

### **Accessing Swagger UI**

Once the application is running, you can access the API documentation via Swagger UI:

```
http://localhost:5000/apidocs/
```

---

## **API Documentation**

The API documentation provides detailed information about the available endpoints, request parameters, and responses.

### **Available Endpoints**

#### **User Model**

- `POST /users`: Create a new user.
- `GET /users`: Retrieve all users.
- `GET /users/<id>`: Retrieve a user by ID.
- `PUT /users/<id>`: Update a user.
- `DELETE /users/<id>`: Delete a user.
- `POST /users/login`: User login endpoint.

#### **Product Model**

- `GET /products/list`: List all products.

---

## **Usage Examples**

### **1. Creating a New User**

**Request:**

```http
POST /users HTTP/1.1
Content-Type: application/json

{
  "name": "Alice",
  "email": "alice@example.com",
  "age": 30
}
```

**Response:**

```json
{
  "id": 1,
  "name": "Alice",
  "email": "alice@example.com",
  "age": 30
}
```

### **2. Retrieving All Users**

**Request:**

```http
GET /users HTTP/1.1
```

**Response:**

```json
[
  {
    "id": 1,
    "name": "Alice",
    "email": "alice@example.com",
    "age": 30
  }
]
```

### **3. User Login**

**Request:**

```http
POST /users/login HTTP/1.1
Content-Type: application/json

{
  "email": "alice@example.com"
}
```

**Response:**

```json
{
  "message": "Login successful"
}
```

### **4. Listing Products**

**Request:**

```http
GET /products/list HTTP/1.1
```

**Response:**

```json
[
  {
    "id": 1,
    "name": "Product A",
    "price": 10.0,
    "description": "Description A"
  },
  {
    "id": 2,
    "name": "Product B",
    "price": 20.0,
    "description": "Description B"
  }
]
```

---

## **Extending the Application**

### **Adding a New Model**

1. **Create a Model File**

   Create a new file in `app/models`, e.g., `order_model.py`.

2. **Define the Model**

   ```python
   # app/models/order_model.py

   from .proto_model import ProtoModel
   from typing import ClassVar

   class Order(ProtoModel):
       storable = True
       __tablename__: ClassVar[str] = 'orders'
       id: int = None
       user_id: int
       product_id: int
       quantity: int
   ```

3. **Register the Model**

   In `app/main.py`, register the new model:

   ```python
   from models.order_model import Order

   # Register the Order model
   register_model(Order, storage=storage_backend)
   ```

4. **Run the Application**

   Rebuild and run the application:

   ```bash
   docker-compose up --build
   ```

   The CRUD endpoints for the `Order` model will be automatically available.

### **Adding Custom Endpoints**

Use the `@expose_route` decorator to add custom endpoints to a model.

```python
@staticmethod
@expose_route('/stats', methods=['GET'])
def get_stats():
    """
    ---
    summary: Get order statistics.
    tags:
      - orders
    responses:
      200:
        description: Order statistics
        content:
          application/json:
            schema:
              type: object
              properties:
                total_orders:
                  type: integer
                total_quantity:
                  type: integer
    """
    # Logic to compute statistics
    stats = {
        "total_orders": 100,
        "total_quantity": 500
    }
    return jsonify(stats), 200
```

---

## **Switching Storage Backends**

The application supports different storage backends through dependency injection.

### **Available Backends**

- **SQLite**: Default relational database.
- **JSON Files**: Simple file-based storage.

### **Switching to JSON Storage**

1. **Import JSONStorage**

   ```python
   from storage.json_storage import JSONStorage
   ```

2. **Instantiate JSONStorage**

   ```python
   storage_backend = JSONStorage(directory='data')
   ```

3. **Run the Application**

   The application will now use JSON files in the specified directory for storage.

---

## **Testing**

Comprehensive tests are provided to ensure the application's functionality.

### **Testing Framework**

- **Pytest**: Used for writing and running tests.
- **pytest-flask**: Provides fixtures for testing Flask applications.

### **Setting Up the Testing Environment**

1. **Install Testing Dependencies**

   Ensure that `pytest` and `pytest-flask` are included in `requirements.txt` and installed.

   ```plaintext
   pytest==7.2.1
   pytest-flask==1.2.0
   ```

2. **Testing Directory**

   Tests are located in the `app/tests` directory.

---

### **Running the Tests**

From the root directory, run:

```bash
pytest
```

This command will discover and run all tests in the `tests` directory.

---

### **Test Coverage**

Tests cover:

- **Model Validation**: Ensuring models accept and reject appropriate data.
- **Storage Operations**: CRUD operations for storable models.
- **API Endpoints**: Testing all API endpoints for correct responses.
- **Error Handling**: Verifying that invalid requests are handled gracefully.

---

## **Test Examples**

### **1. Model Tests**

#### **`test_models.py`**

```python
# app/tests/test_models.py

import pytest
from models.user_model import User
from pydantic import ValidationError

def test_user_creation():
    user = User(name="Bob", email="bob@example.com", age=25)
    assert user.name == "Bob"
    assert user.email == "bob@example.com"
    assert user.age == 25

def test_user_email_validation():
    with pytest.raises(ValidationError):
        User(name="Bob", email="invalid-email", age=25)
```

---

### **2. API Tests**

#### **`test_api.py`**

```python
# app/tests/test_api.py

import pytest
from flask import Flask
from app.main import app as flask_app

@pytest.fixture
def client():
    with flask_app.test_client() as client:
        yield client

def test_create_user(client):
    response = client.post('/users', json={
        'name': 'Charlie',
        'email': 'charlie@example.com',
        'age': 28
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Charlie'
    assert data['email'] == 'charlie@example.com'
    assert data['age'] == 28

def test_get_users(client):
    response = client.get('/users')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)

def test_user_login_success(client):
    client.post('/users', json={
        'name': 'Dana',
        'email': 'dana@example.com',
        'age': 32
    })
    response = client.post('/users/login', json={'email': 'dana@example.com'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == 'Login successful'

def test_user_login_failure(client):
    response = client.post('/users/login', json={'email': 'nonexistent@example.com'})
    assert response.status_code == 401
    data = response.get_json()
    assert data['error'] == 'Invalid credentials'
```

---

### **3. Storage Backend Tests**

#### **`test_storage.py`**

```python
# app/tests/test_storage.py

import pytest
from storage.sqlite_storage import SQLiteStorage
from models.user_model import User

@pytest.fixture
def storage():
    # Use an in-memory SQLite database for testing
    return SQLiteStorage(database=':memory:')

def test_storage_create_and_get_user(storage):
    User.set_storage(storage)
    User.create_table()
    user = User(name="Eve", email="eve@example.com", age=29)
    created_user = User.create(user)
    assert created_user.id is not None

    retrieved_user = User.get_by_id(created_user.id)
    assert retrieved_user.name == "Eve"
    assert retrieved_user.email == "eve@example.com"
    assert retrieved_user.age == 29
```

---

### **Test Coverage Report**

To generate a test coverage report, you can use `pytest-cov`.

1. **Install `pytest-cov`**

   ```bash
   pip install pytest-cov
   ```

2. **Run Tests with Coverage**

   ```bash
   pytest --cov=app tests/
   ```

3. **View Coverage Report**

   The coverage percentage will be displayed in the console. For an HTML report:

   ```bash
   pytest --cov=app --cov-report=html tests/
   ```

   Open `htmlcov/index.html` in a browser to view the detailed coverage report.

---

## **Conclusion**

This documentation provides a comprehensive guide to setting up, running, and extending the application, along with instructions on testing and ensuring code quality. By following this guide, you can confidently use the application, customize it to your needs, and verify its functionality through extensive tests.

---

# **Appendix**

## **Frequently Asked Questions**

### **1. How do I add a new storage backend?**

Implement the `StorageInterface` by creating a new class in the `storage` package. Define all required methods (`create_table`, `create`, `get_all`, `get_by_id`, `update`, `delete`). Then, instantiate and inject it in `main.py`.

### **2. Can I use a database other than SQLite?**

Yes. You can implement a storage backend for databases like PostgreSQL or MongoDB by creating a new class that implements `StorageInterface`.

### **3. How do I handle migrations when changing models?**

The current implementation does not handle migrations automatically. For complex migrations, consider using a dedicated migration tool or ORM that supports migrations.

---

## **Contact Information**

For further assistance or to report issues, please contact the project maintainer:

- **Email**: todo@example.com
- **GitHub**: [todo/yourrepository](https://github.
  com/yourusername/yourrepository)

---
