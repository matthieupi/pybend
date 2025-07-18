# app/models/user_model.py
from __future__ import annotations
from .proto_model import ProtoModel
from typing import ClassVar, Optional
from utils.decorators import expose_route
from flask import request, jsonify

class Bot(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'bots'
    id: int = None
    name: str
    description: str
    owner: str
    version: str
    status: str
    prompt: str


class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    id: int = None
    name: str
    email: str
    age: Optional[int] = None

    @classmethod
    def create(cls, data):
        data.email = data.email.lower()
        return super().create(data)

    @staticmethod
    @expose_route('/login', methods=['POST'])
    def login(email: str, password: str) -> User:
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
        responses:
          200:
            description: Login successful
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    message:
                      type: string
          401:
            description: Unauthorized
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    error:
                      type: string
        """
        users = User.list()
        if any(u.email == email for u in users):
            # Return the found user object
            return next(u for u in users if u.email == email)
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
