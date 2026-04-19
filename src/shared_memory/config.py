import json
import os
from pathlib import Path

from shared_memory.utils import get_logger

logger = get_logger("config")


class Settings:
    """SharedMemoryServerの設定を管理するクラス。"""

    _instance = None
    _base_dir: Path | None = None
    _api_key: str | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Load .env if possible (Leverage python-dotenv if available)
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            logger.debug("python-dotenv not installed; skipping .env loading")

    @property
    def base_dir(self) -> Path:
        """データ保存のベースディレクトリを返す。"""
        if self._base_dir:
            return self._base_dir

        shared_home = os.environ.get("SHARED_MEMORY_HOME")
        if shared_home:
            self._base_dir = Path(shared_home).absolute()
        else:
            # utils.py と同様のロジックでプロジェクトルートを探し、.shared_memory を作成
            from shared_memory.utils import PathResolver

            self._base_dir = Path(PathResolver.get_base_data_dir()).absolute()

        self._base_dir.mkdir(parents=True, exist_ok=True)
        return self._base_dir

    @property
    def db_path(self) -> Path:
        """SQLite データベースのパスを返す。"""
        env_db_path = os.environ.get("MEMORY_DB_PATH")
        if env_db_path:
            return Path(env_db_path).absolute()
        return self.base_dir / "knowledge.db"

    @property
    def thoughts_db_path(self) -> Path:
        """思考プロセスを保存する SQLite データベースのパスを返す。"""
        env_db_path = os.environ.get("THOUGHTS_DB_PATH")
        if env_db_path:
            return Path(env_db_path).absolute()
        return self.base_dir / "thoughts.db"

    @property
    def bank_dir(self) -> Path:
        """Memory Bank のディレクトリパスを返す。"""
        env_bank_dir = os.environ.get("MEMORY_BANK_DIR")
        if env_bank_dir:
            return Path(env_bank_dir).absolute()
        return self.base_dir / "bank"

    @property
    def api_key(self) -> str | None:
        """
        Gemini APIキーの解決。
        順序:
        1. 環境変数 (GOOGLE_API_KEY / GEMINI_API_KEY)
        2. .env ファイル (自動ロード済み)
        3. MCP Global Settings (~/.gemini/settings.json)
        """
        if self._api_key:
            return self._api_key

        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            self._api_key = api_key.strip()
            return self._api_key

        # Fallback to MCP global settings.json
        try:
            settings_path = Path.home() / ".gemini" / "settings.json"
            if settings_path.exists():
                with open(settings_path, encoding="utf-8") as f:
                    settings_json = json.load(f)
                    mcp_env = (
                        settings_json.get("mcpServers", {})
                        .get("SharedMemoryServer", {})
                        .get("env", {})
                    )
                    api_key = mcp_env.get("GOOGLE_API_KEY") or mcp_env.get(
                        "GEMINI_API_KEY"
                    )
                    if not api_key:
                        api_key = (
                            settings_json.get("GOOGLE_API_KEY")
                            or settings_json.get("GEMINI_API_KEY")
                        )

                    if api_key:
                        self._api_key = api_key.strip()
                        return self._api_key
        except Exception as e:
            logger.debug(f"Failed to read settings.json: {e}")

        return None

    @property
    def enable_structured_logging(self) -> bool:
        """構造化ログの有効化フラグ。"""
        return (
            os.environ.get("ENABLE_STRUCTURED_LOGGING", "false").lower()
            == "true"
        )


# Singleton instance
settings = Settings()
