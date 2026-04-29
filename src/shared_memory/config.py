import json
import os
from pathlib import Path

from shared_memory.utils import get_logger

logger = get_logger("config")

# ==========================================
# Generative AI Models (LLM Only)
# ==========================================
# List of models for fallback. Primary is first.
GOOGLE_AI_MODELS = ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]

# Primary model for backward compatibility
GOOGLE_GENERATIVE_MODEL = GOOGLE_AI_MODELS[0]

# ==========================================
# Embedding Model (STRICTLY FIXED)
# ==========================================
# NEVER rotate embedding models as it breaks vector search compatibility.
GOOGLE_EMBEDDING_MODEL = "models/gemini-embedding-001"


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
        # Load .env if possible
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
            # Default to user home
            self._base_dir = Path.home() / ".shared_memory"

        os.makedirs(self._base_dir, exist_ok=True)
        return self._base_dir

    @property
    def api_key(self) -> str | None:
        """Gemini/Google AI APIキーを返す。"""
        if self._api_key:
            return self._api_key

        # 1. Environment variables
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            self._api_key = api_key.strip()
            return self._api_key

        # 2. Claude Desktop config (settings.json) search
        try:
            config_paths = [
                Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json",
                Path.home()
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json",
            ]
            for path in config_paths:
                if path.exists():
                    with open(path, encoding="utf-8") as f:
                        settings_json = json.load(f)

                    # Search in mcpServers -> SharedMemoryServer -> env
                    mcp_env = (
                        settings_json.get("mcpServers", {})
                        .get("SharedMemoryServer", {})
                        .get("env", {})
                    )
                    api_key = mcp_env.get("GOOGLE_API_KEY") or mcp_env.get("GEMINI_API_KEY")

                    if api_key:
                        self._api_key = api_key.strip()
                        return self._api_key
        except Exception as e:
            logger.debug(f"Failed to read settings.json: {e}")

        return None

    @property
    def generative_model(self) -> str:
        """推論や知識抽出に使用する現在の生成モデル名を返す。"""
        # Dynamic rotation support
        from shared_memory.ai_control import model_manager

        return model_manager.get_current_model()

    @property
    def embedding_model(self) -> str:
        """埋め込みベクトル生成に使用するモデル名を返す（固定）。"""
        return GOOGLE_EMBEDDING_MODEL

    @property
    def enable_structured_logging(self) -> bool:
        """構造化ログの有効化フラグ。"""
        return False


# Singleton instance
settings = Settings()
