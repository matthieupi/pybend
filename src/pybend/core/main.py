# app/main.py

from fastapi import FastAPI
from models.product_model import Product
from api.routes import router as api_router, register_routes
from models.user_model import User
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import register_model

app = FastAPI(
    title="PyBend API",
    version="1.0.0",
    description="Modular and extensible backend built with FastAPI"
)

# Set up storage and register models
storage_backend = SQLiteStorage("database.db")
register_model(User, storage=storage_backend)
register_model(Product, storage=storage_backend)
register_routes()

# Include API router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
