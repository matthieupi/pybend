# 🛠️ N3TX: Your Modular API Framework with a Twist

Welcome to N3TX! This is not just another API framework—it’s a highly modular, storage-flexible, and swagger-drenched ecosystem designed for builders who want to have it all. Whether you’re defining models, crafting endpoints, or swapping storage backends, N3TX has got you covered.

---

## 📚 Table of Contents

1. [What is N3TX?](#what-is-n3tx)
2. [Features](#features)
3. [Getting Started](#getting-started)
4. [How It Works](#how-it-works)
5. [Storage Backends](#storage-backends)
6. [Customizing N3TX](#customizing-n3tx)
7. [Testing the System](#testing-the-system)
8. [Contributing](#contributing)
9. [License](#license)

---

## 🌐 What is N3TX?

N3TX is a Flask-based API framework that:
- Simplifies CRUD operation generation.
- Supports dynamic model registration.
- Allows flexible integration with storage backends (SQLite, JSON, or your custom implementation).
- Includes Swagger for automatic API documentation.
- Makes it easy to create custom endpoints with decorators.

In short: It bends to your will, but stays structured enough to keep everything under control.

---

## ⚙️ Features

- **Dynamic Model Management**: Define models once and register them dynamically.
- **Automatic CRUD Endpoints**: Storable models get fully functional endpoints out-of-the-box.
- **Custom Routes**: Add unique functionality with the `@expose_route` decorator.
- **Pluggable Storage**: Switch between SQLite, JSON, or implement your own storage.
- **Swagger Integration**: Auto-generated, interactive API documentation.
- **Test-Driven Development**: Comprehensive test suite included.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Flask 2.x
- Optional: Docker (for containerized deployment)

### Installation

Clone the repository:
```bash
git clone https://github.com/yourusername/n3tx.git
cd n3tx
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the application:
```bash
python app/main.py
```

Visit the Swagger UI at `http://localhost:5000/apidocs/` to explore your API.

---

## 🔧 How It Works

1. **Define Models**: Create models in Python using Pydantic for validation.
2. **Register Models**: Register models using the `register_model` function. If the model is storable, attach a storage backend.
3. **Start the Server**: Endpoints for registered models are automatically available. Custom routes can be added using decorators.
4. **Test & Expand**: Write tests, add features, and customize behavior as needed.

---

## 💾 Storage Backends

N3TX provides an abstract storage interface, making it easy to use different storage solutions. Supported backends include:

- **SQLite**: Reliable, fast, and file-based.
- **JSON**: Lightweight, human-readable, and great for quick setups.

To switch backends, simply inject a new storage class during model registration:

```python
from app.storage.json_storage import JSONStorage
from app.storage.sqlite_storage import SQLiteStorage

storage_backend = JSONStorage(directory='data')  # Or SQLiteStorage(database='my.db')
register_model(User, storage=storage_backend)
```

---

## 🛠️ Customizing N3TX

### Adding Models

1. Define your model in `app/models`:
   ```python
   from .proto_model import ProtoModel
   from typing import ClassVar

   class Order(ProtoModel):
       __storable__: ClassVar[bool] = True
       __tablename__: ClassVar[str] = 'orders'
       id: int
       product_id: int
       quantity: int
   ```

2. Register the model in `main.py`:
   ```python
   from app.models.order_model import Order
   register_model(Order, storage=storage_backend)
   ```

3. Start the server and use the auto-generated CRUD endpoints!

### Adding Custom Routes

Decorate methods with `@expose_route` to create custom endpoints:
```python
@staticmethod
@expose_route('/stats', methods=['GET'])
def get_stats():
    return jsonify({'message': 'Statistics are fun!'}), 200
```

---

## 🧪 Testing the System

N3TX includes a comprehensive test suite using `pytest` and `pytest-flask`.

### Run Tests

To run the tests, simply execute:
```bash
pytest
```

### Coverage

For a coverage report:
```bash
pytest --cov=app --cov-report=html
```

Open the HTML report in your browser to explore test coverage.

---

## 🤝 Contributing

Contributions are welcome! Here’s how you can help:

1. Fork the repo and clone it.
2. Create a new branch for your feature or bugfix.
3. Write your code and tests.
4. Submit a pull request.

---

## 📜 License

This project is licensed under the MIT License. See the LICENSE file for details.

---

Happy bending! 🛠️

