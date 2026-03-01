# models/base_user.py
"""
Abstract base user model providing reusable authentication logic.

Subclass this to get login, register, and password hashing out of the box.
Only add app-specific fields (image, age, etc.) and configuration in the
concrete subclass.

Example:
    class User(BaseUser):
        __tablename__ = 'users'
        __abstract__ = False
        image: Optional[str] = Field(default=None)
"""
from __future__ import annotations
import logging
from typing import ClassVar, Optional
from pydantic import Field, field_validator
from .proto_model import ProtoModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import ANYONE, hash_password, verify_password, create_token

logger = logging.getLogger('pybend.models')


class BaseUser(ProtoModel):
    """
    Abstract base model for user entities with built-in auth support.

    Provides:
      - Core identity fields: name, email, role, password_hash
      - Password hashing on create
      - Login endpoint (POST /login) returning JWT token
      - Registration endpoint (POST /register) returning JWT token

    Subclasses MUST set:
      - __tablename__  (e.g. 'users')
      - __abstract__ = False  (to mark as concrete / registrable)

    Subclasses MAY add:
      - App-specific fields (image, age, bio, ...)
      - __ui__, __access__, and other model-level configuration
    """

    __storable__: ClassVar[bool] = True
    __abstract__: ClassVar[bool] = True
    __owner_field__: ClassVar[str] = 'id'
    __hidden_fields__: ClassVar[set] = {'password_hash'}

    name: str
    email: str
    role: str = Field(default='user', description="User role: user, admin, moderator")
    password_hash: Optional[str] = Field(default=None, exclude=True)

    @field_validator('role', mode='before')
    @classmethod
    def _coerce_role(cls, v):
        if v is None or v == '' or v == "''":
            return 'user'
        return v

    # --- Auth methods (use cls so subclasses inherit correctly) ---

    @classmethod
    def create(cls, data):
        """Hash password before storing."""
        data.email = data.email.lower()
        # If a plain password was stashed on the instance, hash it
        plain_pw = getattr(data, '_plain_password', None)
        if plain_pw:
            data.password_hash = hash_password(plain_pw)
        return super().create(data)

    @classmethod
    @expose_route('/login', methods=['POST'], access=ANYONE)
    def login(cls, email: str, password: str) -> dict:
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
        users = cls.list()
        user = next((u for u in users if u.email == email), None)
        if not user or not user.password_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_token(user.id, user.email, user.role)
        return {"token": token, "user": user.model_response()}

    @classmethod
    @expose_route('/register', methods=['POST'], access=ANYONE)
    def register_user(cls, name: str, email: str, password: str) -> dict:
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
        existing = cls.list()
        if any(u.email == email for u in existing):
            raise HTTPException(status_code=409, detail="Email already registered")
        # Create user with hashed password
        user = cls(name=name, email=email)
        user._plain_password = password
        created = cls.create(user)
        token = create_token(created.id, created.email, created.role)
        return {"token": token, "user": created.model_response()}
