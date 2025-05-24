from typing import Any, ClassVar

from utils.registrar import registered_models

# app/adapters/base_adapter.py

from abc import ABC, abstractmethod

from pydantic import BaseModel

class BaseBackend(ABC, BaseModel):
    """
    Base model for backend adapters.
    """
    name: str
    description: str
    version: str
    port: int = 8000

    app: Any = None
    registered_models: dict[str, type] = {}

    class Config:
        orm_mode = True

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.registered_models = registered_models
        self.name = self.__class__.__name__.lower()
        self.description = f"{self.__class__.__name__} backend"
        self.version = "1.0.0"
        self.port = 8000

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


    @abstractmethod
    def register_routes(self, registered_models: dict[str, type]):
        pass


# app/backends/fastapi_backend.py
class FastAPIBackend(BaseBackend):
    def __init__(self, **data):
        super().__init__(**data)
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        self.app = FastAPI(
            title=self.name,
            version=self.version,
            description=self.description
        )
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def register_routes(self, registered_models: dict[str, type]):
        from api.routes_fastapi import register_routes
        from api.routes_fastapi import router
        register_routes()
        self.app.include_router(router)

    def get_app(self):
        return self.app


# app/backends/flask_backend.py
class FlaskBackend(BaseBackend):
    def __init__(self, **data):
        super().__init__(**data)
        from flask import Flask
        from flasgger import Swagger
        self.app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')
        self.app.config['SWAGGER'] = {'title': 'PyBend Flask API', 'uiversion': 3}
        Swagger(self.app)

    def register_routes(self, registered_models: dict[str, type]):
        from api.routes_flask import create_api_blueprint
        blueprint = create_api_blueprint(registered_models)
        self.app.register_blueprint(blueprint)

    def get_app(self):
        from asgiref.wsgi import WsgiToAsgi
        return WsgiToAsgi(self.app)

