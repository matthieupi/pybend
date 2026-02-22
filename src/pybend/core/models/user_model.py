# app/models/user_model.py
from __future__ import annotations
from .proto_model import ProtoModel
from typing import ClassVar, Optional
from pydantic import Field, field_validator
from utils.decorators import expose_route
from authorize import ANYONE, hash_password, verify_password, create_token


class Bot(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'bots'
    name: str
    description: str
    owner: str
    version: str
    status: str
    prompt: str


class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    image: str = Field(default='https://ui-avatars.com/api/?name=User&background=94a3b8&color=fff&size=128&rounded=true')
    name: str
    email: str
    role: str = Field(default='user', description="User role: user, admin, moderator")

    @field_validator('role', mode='before')
    @classmethod
    def _coerce_role(cls, v):
        if v is None or v == '' or v == "''":
            return 'user'
        return v

    age: Optional[int] = None
    password_hash: Optional[str] = Field(default=None, exclude=True)

    # Fields to hide from schema (exclude=True handles serialization)
    __hidden_fields__: ClassVar[set] = {'password_hash'}

    @classmethod
    def create(cls, data):
        data.email = data.email.lower()
        # If a plain password was stashed on the instance, hash it
        plain_pw = getattr(data, '_plain_password', None)
        if plain_pw:
            data.password_hash = hash_password(plain_pw)
        return super().create(data)

    @staticmethod
    @expose_route('/login', methods=['POST'], access=ANYONE)
    def login(email: str, password: str) -> dict:
        """
        User login endpoint.
        ---
        tags:
          - users
        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                properties:
                  email:
                    type: string
                  password:
                    type: string
        responses:
          200:
            description: Login successful
          401:
            description: Unauthorized
        """
        from fastapi import HTTPException
        email = email.lower()
        users = User.list()
        user = next((u for u in users if u.email == email), None)
        if not user or not user.password_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_token(user.id, user.email, user.role)
        return {"token": token, "user": user.model_dump(response=True)}

    @staticmethod
    @expose_route('/register', methods=['POST'], access=ANYONE)
    def register(name: str, email: str, password: str) -> dict:
        """
        User registration endpoint.
        ---
        tags:
          - users
        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                properties:
                  name:
                    type: string
                  email:
                    type: string
                  password:
                    type: string
        responses:
          201:
            description: Registration successful
          409:
            description: Email already registered
        """
        from fastapi import HTTPException
        email = email.lower()
        # Check uniqueness
        existing = User.list()
        if any(u.email == email for u in existing):
            raise HTTPException(status_code=409, detail="Email already registered")
        # Create user with hashed password
        user = User(name=name, email=email)
        user._plain_password = password
        created = User.create(user)
        token = create_token(created.id, created.email, created.role)
        return {"token": token, "user": created.model_dump(response=True)}
