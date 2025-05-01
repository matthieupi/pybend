# app/main.py

from fastapi import FastAPI
from models.product_model import Product
from api.backend import FastAPIBackend, FlaskBackend
from models.user_model import User
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import register_model, registered_models

BACKEND = "fastapi"  # or "flask"

# Set up storage and register models
storage_backend = SQLiteStorage("database.db")
register_model(User, storage=storage_backend)
register_model(Product, storage=storage_backend)

if BACKEND == "flask":
    backend = FlaskBackend(
        name="PyBend Flask API",
        version="1.0.0",
        description="Modular and extensible backend built with Flask",
        port=8000
    )
    backend.register_routes(registered_models)
    app = backend.get_app()
elif BACKEND == "fastapi":
    # FastAPI backend setup
    backend = FastAPIBackend(
        name="PyBend FastAPI",
        version="1.0.0",
        description="Modular and extensible backend built with FastAPI",
        port=8000
    )
    backend.register_routes(registered_models)
    app = backend.get_app()

else:
    raise ValueError(f"Unsupported backend: {BACKEND}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
