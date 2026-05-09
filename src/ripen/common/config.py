import json
import os
from pathlib import Path
from typing import Any

from ripen.common.utils import get_logger

logger = get_logger("config")

# ==========================================
# AI Model Configuration (LLM & Embeddings)
# ==========================================

# Default Engines (Local-first)
DEFAULT_EMBEDDING_ENGINE = "fastembed"
DEFAULT_LLM_PROVIDER = "ollama"

# Gemini Settings (Optional)
GOOGLE_AI_MODELS = ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]
GOOGLE_COMPRESSION_MODELS = ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]
GOOGLE_EMBEDDING_MODEL = "models/gemini-embedding-001"

# Ollama Settings (Local host)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")

# FastEmbed Settings (Local vectorization)
FASTEMBED_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class Settings:
    """Ripenの設定を管理するクラス。"""

    _instance = None
    _base_dir: Path | None = None
    _api_key: str | None = None
    _config_data: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 1. Load .env if possible
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            logger.debug("python-dotenv not installed; skipping .env loading")

        # 2. Load config.json if it exists
        self._load_config_json()

    def _load_config_json(self):
        """base_dirにあるconfig.jsonを読み込む。"""
        config_path = self.base_dir / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self._config_data = json.load(f)
                logger.info(f"Loaded config from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config.json: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """環境変数 > config.json > デフォルトの順で設定値を取得する。"""
        # 環境変数は大文字でチェック
        env_val = os.environ.get(key.upper())
        if env_val is not None:
            return env_val
        
        # config.jsonは小文字キーでチェック
        return self._config_data.get(key.lower(), default)

    @property
    def base_dir(self) -> Path:
        """データ保存のベースディレクトリを返す。"""
        if self._base_dir:
            return self._base_dir

        shared_home = os.environ.get("RIPEN_HOME") or os.environ.get("SHARED_MEMORY_HOME")
        if shared_home:
            self._base_dir = Path(shared_home).absolute()
        else:
            # Default to user home
            self._base_dir = Path.home() / ".ripen"

        os.makedirs(self._base_dir, exist_ok=True)
        return self._base_dir

    @property
    def api_key(self) -> str | None:
        """Gemini/Google AI APIキーを返す。"""
        if self._api_key:
            return self._api_key

        # 1. Environment variables or config.json
        api_key = self.get("GOOGLE_API_KEY") or self.get("GEMINI_API_KEY")
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

                    # Search in mcpServers -> Ripen -> env
                    # Also check for "SharedMemoryServer" for backward compatibility
                    server_names = ["Ripen", "SharedMemoryServer"]
                    for name in server_names:
                        mcp_env = (
                            settings_json.get("mcpServers", {})
                            .get(name, {})
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
    def embedding_engine(self) -> str:
        """使用するEmbeddingエンジンを返す (fastembed or gemini)。"""
        engine = self.get("EMBEDDING_ENGINE", DEFAULT_EMBEDDING_ENGINE).lower()
        # Force gemini if API key is present and engine is explicitly gemini,
        # otherwise default to fastembed.
        if engine == "gemini" and self.api_key:
            return "gemini"
        return "fastembed"

    @property
    def llm_provider(self) -> str:
        """使用するLLMプロバイダーを返す (ollama or gemini or none)。"""
        # 1. Explicit environment variable or config.json
        provider = self.get("LLM_PROVIDER")
        if provider:
            return provider.lower()

        # 2. Prefer Gemini if API Key is present (Auto-detect)
        if self.api_key:
            return "gemini"

        # 3. Fallback to default
        return DEFAULT_LLM_PROVIDER

    @property
    def generative_model(self) -> str:
        """推論や知識抽出に使用する現在の生成モデル名を返す。"""
        if self.llm_provider == "ollama":
            return self.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)

        # Dynamic rotation support for Gemini
        from ripen.core.ai_control import model_manager

        return model_manager.get_current_model()

    @property
    def embedding_model(self) -> str:
        """埋め込みベクトル生成に使用するモデル名を返す。"""
        if self.embedding_engine == "gemini":
            return GOOGLE_EMBEDDING_MODEL
        return FASTEMBED_DEFAULT_MODEL

    @property
    def ollama_base_url(self) -> str:
        """OllamaのAPIベースURLを返す。"""
        return self.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL)

    @property
    def enable_structured_logging(self) -> bool:
        """構造化ログの有効化フラグ。"""
        return self.get("ENABLE_STRUCTURED_LOGGING", "false").lower() == "true"

    @property
    def hashtag_ai_threshold(self) -> int:
        """ハッシュタグ抽出においてAIを使用するかロジックを使用するかの文字数閾値。"""
        return int(self.get("HASHTAG_AI_THRESHOLD", "100"))


# Singleton instance
settings = Settings()
