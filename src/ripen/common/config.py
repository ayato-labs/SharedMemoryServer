import json
import os
from pathlib import Path
from typing import Any, ClassVar

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
    _config_data: ClassVar[dict] = {}
    _plugins: ClassVar[list] = []
    # --- Licensing ---
    license_public_key: str = os.getenv(
        "RIPEN_LICENSE_PUBLIC_KEY", "vF9JtiTPlurcpy6F4UywkLdyisrHXEaU75CjeCVvZfg="
    )

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
                with open(config_path, encoding="utf-8") as f:
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
            # Use os.path.expanduser to be more robust than Path.home() in some environments
            self._base_dir = Path(os.path.expanduser("~")) / ".ripen"

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

        return None

    @property
    def embedding_engine(self) -> str:
        """使用するEmbeddingエンジンを返す (fastembed or gemini)。"""
        engine = self.get("EMBEDDING_ENGINE", DEFAULT_EMBEDDING_ENGINE).lower()
        if engine == "gemini" and self.api_key:
            return "gemini"
        return "fastembed"

    @property
    def llm_provider(self) -> str:
        """使用するLLMプロバイダーを返す (ollama or gemini or none)。"""
        provider = self.get("LLM_PROVIDER")
        if provider:
            return provider.lower()
        return DEFAULT_LLM_PROVIDER


    @property
    def ollama_base_url(self) -> str:
        """OllamaのベースURLを返す。"""
        return self.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL)

    @property
    def ollama_model(self) -> str:
        """Ollamaで使用するデフォルトモデルを返す。"""
        return self.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)

    @property
    def fastembed_model(self) -> str:
        """FastEmbedで使用するデフォルトモデルを返す。"""
        return self.get("FASTEMBED_MODEL", FASTEMBED_DEFAULT_MODEL)

    @property
    def google_ai_model(self) -> str:
        """Google AIで使用するモデルを返す。"""
        return GOOGLE_AI_MODELS[0]

    @property
    def google_compression_model(self) -> str:
        """Google AIで使用する圧縮用モデルを返す。"""
        return GOOGLE_COMPRESSION_MODELS[0]

    @property
    def google_embedding_model(self) -> str:
        """Google AIで使用するEmbeddingモデルを返す。"""
        return GOOGLE_EMBEDDING_MODEL

    @property
    def embedding_model(self) -> str:
        """現在選択されているエンジンに応じたEmbeddingモデル名を返す。"""
        if self.embedding_engine == "fastembed":
            return self.fastembed_model
        return self.google_embedding_model

    @property
    def generative_model(self) -> str:
        """現在選択されているプロバイダーに応じた生成モデル名を返す。"""
        if self.llm_provider == "ollama":
            return self.ollama_model
        
        # Avoid circular import by importing inside the property
        try:
            from ripen.core.ai_control import model_manager
            return model_manager.get_current_model("generation")
        except (ImportError, Exception):
            # Fallback to default if model_manager is not available
            return GOOGLE_AI_MODELS[0]

    @property
    def log_level(self) -> str:
        """ログレベルを返す。"""
        return self.get("LOG_LEVEL", "INFO").upper()

    @property
    def plugins(self) -> list:
        """ロードされたプラグインのリストを返す。"""
        return self._plugins

    @property
    def is_enterprise(self) -> bool:
        """商用版プラグインが有効かどうかを返す。"""
        return any(getattr(p, "is_enterprise", False) for p in self._plugins)

    @property
    def default_transport(self) -> str:
        """デフォルトの通信方式 (stdio or sse) を返す。"""
        return self.get("DEFAULT_TRANSPORT", "stdio").lower()

    @property
    def sse_port(self) -> int:
        """SSEモードで使用するポート番号を返す。"""
        return int(self.get("SSE_PORT", "8377"))

    @property
    def db_path(self) -> Path:
        """メインデータベースのパスを返す。"""
        # 1. Environment variable
        env_path = os.environ.get("MEMORY_DB_PATH")
        if env_path:
            return Path(env_path).absolute()

        # 2. Config home
        return self.base_dir / "knowledge.db"

    @property
    def thoughts_db_path(self) -> Path:
        """思考履歴データベースのパスを返す。"""
        # 1. Environment variable
        env_path = os.environ.get("THOUGHTS_DB_PATH")
        if env_path:
            return Path(env_path).absolute()

        # 2. Config home
        return self.base_dir / "thoughts.db"

    @property
    def license_key_path(self) -> Path:
        """ライセンスファイルの保存パスを返す。"""
        return self.base_dir / "license.rpn"

    @property
    def hashtag_ai_threshold(self) -> int:
        """AIによるハッシュタグ抽出を行う閾値(文字数)。"""
        return int(self.get("HASHTAG_AI_THRESHOLD", "100"))

    @property
    def stale_access_threshold(self) -> int:
        """GC対象とする低頻度アクセスの閾値。"""
        return int(self.get("STALE_ACCESS_THRESHOLD", "5"))

    @property
    def default_gc_age_days(self) -> int:
        """デフォルトのGC対象日数。"""
        return int(self.get("DEFAULT_GC_AGE_DAYS", "180"))


# Global settings instance
settings = Settings()
