from typing import Optional


class AccessDenied(Exception):
    """Raised when an authorization rule denies access."""

    def __init__(self, action: str, model: str, user_id: Optional[int] = None, detail: str = None):
        self.action = action
        self.model = model
        self.user_id = user_id
        self.detail = detail or f"Access denied: {action} on {model} for user {user_id}"
        super().__init__(self.detail)
