import json
import os
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from shared_memory.common.utils import get_logger

logger = get_logger("auth")

# Context variable to hold the authenticated account name for the current request/task
current_user: ContextVar[Optional[str]] = ContextVar("current_user", default=None)

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_file_path: str = "data/auth.json"):
        super().__init__(app)
        self.auth_file_path = auth_file_path
        self._load_auth_data()

    def _load_auth_data(self):
        """Loads account:api_key pairs from the auth file."""
        if not os.path.exists(self.auth_file_path):
            logger.warning(f"Auth file not found at {self.auth_file_path}. Authentication will be disabled or fail.")
            self.auth_data = {}
            return
        
        try:
            with open(self.auth_file_path, "r", encoding="utf-8") as f:
                self.auth_data = json.load(f)
            logger.info(f"Loaded {len(self.auth_data)} accounts from {self.auth_file_path}")
        except Exception as e:
            logger.error(f"Failed to load auth file: {e}")
            self.auth_data = {}

    async def dispatch(self, request, call_next):
        # 1. Check for API Key in headers (X-API-Key or Authorization)
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]

        # 2. If no key, and it's SSE/POST, we might want to be strict
        # For now, let's look up the account
        account_name = None
        if api_key:
            for acc, key in self.auth_data.items():
                if key == api_key:
                    account_name = acc
                    break

        if not account_name:
            # Check if SHARED_MEMORY_API_KEY environment variable is set as a fallback for local dev
            env_key = os.environ.get("SHARED_MEMORY_API_KEY")
            env_acc = os.environ.get("SHARED_MEMORY_ACCOUNT", "default_env_user")
            if env_key and api_key == env_key:
                account_name = env_acc

        if not account_name:
            # If authentication is required but missing/invalid
            # We allow the request to proceed but current_user will be None
            # The tools can then decide to reject or use a default
            logger.debug(f"Unauthenticated request to {request.url.path}")
        else:
            logger.debug(f"Authenticated request from account: {account_name}")

        # Set the context variable
        token = current_user.set(account_name)
        try:
            response = await call_next(request)
            return response
        finally:
            current_user.reset(token)

def get_current_user() -> Optional[str]:
    """Returns the authenticated account name for the current context."""
    return current_user.get()
