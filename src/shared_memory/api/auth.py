import json
import os
from contextvars import ContextVar

from starlette.responses import JSONResponse  # noqa: F401

from shared_memory.common.utils import get_logger

logger = get_logger("auth")

# Context variable to hold the authenticated account name for the current request/task
current_user: ContextVar[str | None] = ContextVar("current_user", default=None)


class AuthMiddleware:
    def __init__(self, app, auth_file_path: str = "data/auth.json"):
        self.app = app
        self.auth_file_path = auth_file_path
        self._load_auth_data()

    def _load_auth_data(self):
        """Loads account:api_key pairs from the auth file."""
        if not os.path.exists(self.auth_file_path):
            logger.warning(
                f"Auth file not found at {self.auth_file_path}. "
                "Authentication will be disabled or fail."
            )
            self.auth_data = {}
            return

        try:
            with open(self.auth_file_path, encoding="utf-8") as f:
                self.auth_data = json.load(f)
            logger.info(f"Loaded {len(self.auth_data)} accounts from {self.auth_file_path}")
        except Exception as e:
            logger.error(f"Failed to load auth file: {e}")
            self.auth_data = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # 1. Extract API Key from headers directly from scope
        api_key = None
        headers = dict(scope.get("headers", []))

        # Headers are byte strings in scope
        x_api_key = headers.get(b"x-api-key")
        if x_api_key:
            api_key = x_api_key.decode()
        else:
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]

        # 2. Look up the account
        account_name = None
        if api_key:
            for acc, key in self.auth_data.items():
                if key == api_key:
                    account_name = acc
                    break

        if not account_name:
            # Check if SHARED_MEMORY_API_KEY environment variable is set as a fallback
            env_key = os.environ.get("SHARED_MEMORY_API_KEY")
            env_acc = os.environ.get("SHARED_MEMORY_ACCOUNT", "default_env_user")
            if env_key and api_key == env_key:
                account_name = env_acc

        if not account_name:
            path = scope.get("path", "")
            logger.debug(f"Unauthenticated request to {path}")
        else:
            logger.debug(f"Authenticated request from account: {account_name}")

        # Set the context variable
        token = current_user.set(account_name)
        try:
            return await self.app(scope, receive, send)
        finally:
            current_user.reset(token)


def get_current_user() -> str | None:
    """Returns the authenticated account name for the current context."""
    return current_user.get()
