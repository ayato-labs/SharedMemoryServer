import json
import os
from abc import ABC, abstractmethod
from contextvars import ContextVar

from ripen.common.utils import get_logger

logger = get_logger("auth")

# Context variable to hold the authenticated account name for the current request/task
current_user: ContextVar[str | None] = ContextVar("current_user", default=None)


class IAuthProvider(ABC):
    """Interface for authentication providers."""

    @abstractmethod
    async def authenticate(self, api_key: str) -> str | None:
        """
        Authenticates a request using an API key.
        Returns the account name if successful, else None.
        """
        pass


class LocalFileAuthProvider(IAuthProvider):
    """Auth provider that uses a local JSON file (auth.json)."""

    def __init__(self, auth_file_path: str = "data/auth.json"):
        self.auth_file_path = auth_file_path
        self.auth_data = {}
        self._load_auth_data()

    def _load_auth_data(self):
        if not os.path.exists(self.auth_file_path):
            logger.warning(f"Auth file not found at {self.auth_file_path}")
            return
        try:
            with open(self.auth_file_path, encoding="utf-8") as f:
                self.auth_data = json.load(f)
            logger.info(f"Loaded {len(self.auth_data)} accounts from {self.auth_file_path}")
        except Exception as e:
            logger.error(f"Failed to load auth file: {e}")

    async def authenticate(self, api_key: str) -> str | None:
        for acc, key in self.auth_data.items():
            if key == api_key:
                return acc
        return None


class EnvAuthProvider(IAuthProvider):
    """Auth provider that uses environment variables."""

    async def authenticate(self, api_key: str) -> str | None:
        env_key = os.environ.get("RIPEN_API_KEY") or os.environ.get("SHARED_MEMORY_API_KEY")
        env_acc = os.environ.get("RIPEN_ACCOUNT") or os.environ.get(
            "SHARED_MEMORY_ACCOUNT", "default_env_user"
        )
        if env_key and api_key == env_key:
            return env_acc
        return None


class AuthMiddleware:
    """ASGI middleware for authentication using pluggable providers."""

    def __init__(self, app, providers: list[IAuthProvider] | None = None):
        self.app = app
        self.providers = providers or [LocalFileAuthProvider(), EnvAuthProvider()]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # 1. Extract API Key
        api_key = None
        headers = dict(scope.get("headers", []))

        x_api_key = headers.get(b"x-api-key")
        if x_api_key:
            api_key = x_api_key.decode()
        else:
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]

        # 2. Try each provider
        account_name = None
        if api_key:
            for provider in self.providers:
                account_name = await provider.authenticate(api_key)
                if account_name:
                    break

        if account_name:
            logger.debug(f"Authenticated request from: {account_name}")
        else:
            logger.debug(f"Unauthenticated request to {scope.get('path', '')}")

        # 3. Set context and continue
        token = current_user.set(account_name)
        try:
            return await self.app(scope, receive, send)
        finally:
            current_user.reset(token)


def get_current_user() -> str | None:
    """Returns the authenticated account name for the current context."""
    return current_user.get()
