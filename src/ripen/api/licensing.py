import base64
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from ripen.common.config import settings
from ripen.common.utils import get_logger

logger = get_logger("licensing")

class LicenseManager:
    """ライセンス管理を行うクラス。オフライン署名検証に対応。"""

    def __init__(self):
        self.license_path = settings.license_key_path
        self.public_key_base64 = settings.license_public_key
        self._cached_license_info = None

    def _get_public_key(self) -> ed25519.Ed25519PublicKey:
        """Base64形式の公開鍵をオブジェクトに変換する。"""
        public_bytes = base64.b64decode(self.public_key_base64)
        return ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)

    def validate_locally(self) -> bool:
        """
        ローカルに保存されたライセンスを検証する。
        ライセンスがない場合は、試用期間内かどうかをチェックする。
        """
        # 1. Check for license file
        if not self.license_path.exists():
            logger.debug("No license file found. Checking trial status.")
            return self._check_trial_status()

        try:
            # 2. Read and Verify License
            with open(self.license_path, "rb") as f:
                signed_data = f.read()

            # The file format is [signature(64 bytes)][json_payload]
            if len(signed_data) <= 64:
                logger.error("Invalid license file format (too short)")
                return self._check_trial_status()

            signature = signed_data[:64]
            payload_bytes = signed_data[64:]

            # Verify signature
            public_key = self._get_public_key()
            try:
                public_key.verify(signature, payload_bytes)
            except InvalidSignature:
                logger.error("License signature verification failed")
                return self._check_trial_status()

            # 3. Parse and Check Expiry
            payload = json.loads(payload_bytes.decode('utf-8'))
            self._cached_license_info = payload

            expiry_str = payload.get("expiry")
            if not expiry_str:
                logger.error("License missing expiry field")
                return self._check_trial_status()

            expiry_date = datetime.fromisoformat(expiry_str)
            if datetime.now() > expiry_date:
                logger.warning(f"License expired on {expiry_date}")
                return self._check_trial_status()

            logger.info(f"Valid license found. Registered to: {payload.get('user', 'Unknown')}")
            return True

        except Exception as e:
            logger.error(f"Error during local license validation: {e}")
            return self._check_trial_status()

    def activate(self, license_key_path: str | Path) -> bool:
        """
        外部のライセンスファイルを取り込んで有効化する。
        """
        source_path = Path(license_key_path)
        if not source_path.exists():
            logger.error(f"Provided license file not found: {license_key_path}")
            return False

        try:
            # Copy to app directory
            import shutil
            shutil.copy2(source_path, self.license_path)
            
            # Re-validate
            return self.validate_locally()
        except Exception as e:
            logger.error(f"Failed to activate license: {e}")
            return False

    def _check_trial_status(self) -> bool:
        """
        180日間の試用期間内かどうかをチェックする。
        """
        trial_marker = settings.base_dir / ".trial_start"
        
        if not trial_marker.exists():
            # First run, create marker
            with open(trial_marker, "w") as f:
                f.write(datetime.now().isoformat())
            return True

        try:
            with open(trial_marker, "r") as f:
                start_str = f.read().strip()
            start_date = datetime.fromisoformat(start_str)
            
            trial_days = 180
            expiry_date = start_date + timedelta(days=trial_days)
            
            if datetime.now() < expiry_date:
                logger.debug(f"Within trial period. Remaining days: {(expiry_date - datetime.now()).days}")
                return True
            else:
                logger.warning("Trial period has expired.")
                return False
        except Exception:
            return False

    @property
    def info(self) -> dict:
        """現在のライセンス情報を返す。"""
        if self._cached_license_info:
            return self._cached_license_info
        return {"type": "trial", "status": "active" if self._check_trial_status() else "expired"}
