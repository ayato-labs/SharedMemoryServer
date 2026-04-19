import json
import os
from pathlib import Path
from typing import Optional


class Settings:
    """
    SharedMemoryServer の集中設定管理クラス。
    環境変数、.env、およびシステム設定からの読み込みを一元化します。
    """

    def __init__(self):
        self._base_dir: Optional[Path] = None
        self._api_key: Optional[str] = None
        
        # Load .env if possible (Leverage python-dotenv if available)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

    @property
    def base_dir(self) -> Path:
        """
        全データの保存先ベースディレクトリ。
        1. SHARED_MEMORY_HOME 環境変数
        2. プロジェクトルート内の .shared_memory ディレクトリ
        の順で解決します。
        """
        if self._base_dir:
            return self._base_dir

        env_dir = os.environ.get("SHARED_MEMORY_HOME")
        if env_dir:
            self._base_dir = Path(env_dir).absolute()
        else:
            # utils.py と同様のロジックでプロジェクトルートを探し、.shared_memory を作成
            from shared_memory.utils import PathResolver
            self._base_dir = Path(PathResolver.get_base_data_dir()).absolute()
        
        self._base_dir.mkdir(parents=True, exist_ok=True)
        return self._base_dir

    @property
    def db_path(self) -> Path:
        """知識データベースのパス。"""
        env_val = os.environ.get("MEMORY_DB_PATH")
        if env_val:
            return Path(env_val).absolute()
        return self.base_dir / "knowledge.db"

    @property
    def thoughts_db_path(self) -> Path:
        """思考プロセスのパス。"""
        env_val = os.environ.get("THOUGHTS_DB_PATH")
        if env_val:
            return Path(env_val).absolute()
        return self.base_dir / "thoughts.db"

    @property
    def bank_dir(self) -> Path:
        """メモリバンク（Markdown）のディレクトリパス。"""
        env_val = os.environ.get("MEMORY_BANK_DIR")
        if env_val:
            return Path(env_val).absolute()
        return self.base_dir / "bank"

    @property
    def api_key(self) -> Optional[str]:
        """
        Gemini APIキーの解決。
        順序: 
        1. 環境変数 (GOOGLE_API_KEY / GEMINI_API_KEY)
        2. .env ファイル (自動ロード済み)
        3. MCP Global Settings (~/.gemini/settings.json)
        """
        if self._api_key:
            return self._api_key

        # 1 & 2: Env / .env
        key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if key:
            self._api_key = key.strip()
            return self._api_key

        # 3: MCP Settings fallback
        home = Path.home()
        global_settings_path = home / ".gemini" / "settings.json"
        if global_settings_path.exists():
            try:
                with open(global_settings_path, encoding="utf-8") as f:
                    settings = json.load(f)
                    mcp_env = (
                        settings.get("mcpServers", {})
                        .get("SharedMemoryServer", {})
                        .get("env", {})
                    )
                    api_key = mcp_env.get("GOOGLE_API_KEY") or mcp_env.get("GEMINI_API_KEY")
                    if not api_key:
                        api_key = settings.get("GOOGLE_API_KEY") or settings.get("GEMINI_API_KEY")
                    
                    if api_key:
                        self._api_key = api_key.strip()
                        return self._api_key
            except Exception:
                pass

        return None

    @property
    def embedding_model(self) -> str:
        return os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")

    @property
    def dimensionality(self) -> int:
        return int(os.environ.get("EMBEDDING_DIMENSIONALITY", "768"))

    @property
    def enable_structured_logging(self) -> bool:
        return os.environ.get("ENABLE_STRUCTURED_LOGGING", "true").lower() == "true"


# シングルトンインスタンスを提供
settings = Settings()
