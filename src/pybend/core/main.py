# app/main.py

from fastapi import FastAPI

import config
from api.routes_fastapi import register_route
from models.product_model import Product
from api.backend import FastAPIBackend, FlaskBackend
from models.user_model import User
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import register_model, registered_models


# Set up storage and register models
storage_backend = SQLiteStorage(config.SQLITE_DB_FILE)
register_model(Product, storage=storage_backend)
register_model(User, storage=storage_backend)

if config.BACKEND == "flask":
    backend = FlaskBackend(
        name="PyBend Flask API",
        version=config.VERSION,
        description="Modular and extensible backend built with Flask",
        port=config.PORT
    )
    backend.register_routes(registered_models)
    app = backend.get_app()
elif config.BACKEND == "fastapi":
    # FastAPI backend setup
    backend = FastAPIBackend(
        name="PyBend FastAPI",
        version=config.VERSION,
        description="Modular and extensible backend built with FastAPI",
        port=config.PORT
    )
    backend.register_routes(registered_models)
    app = backend.get_app()

else:
    raise ValueError(f"Unsupported backend: {config.BACKEND}")

register_route("/blueprint", lambda: {"name": "ROOT","message": "This is a root route for the API"}, method='GET')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
