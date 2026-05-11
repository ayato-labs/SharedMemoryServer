import base64
import json
import argparse
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519

def generate_license(private_key_base64, user_name, expiry_days=365, output_file="license.rpn"):
    """
    署名済みライセンスファイルを生成する。
    """
    # 1. Prepare Payload
    expiry_date = datetime.now() + timedelta(days=expiry_days)
    payload = {
        "user": user_name,
        "expiry": expiry_date.isoformat(),
        "type": "professional",
        "issued_at": datetime.now().isoformat()
    }
    payload_json = json.dumps(payload).encode('utf-8')

    # 2. Sign Payload
    private_bytes = base64.b64decode(private_key_base64)
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
    
    signature = private_key.sign(payload_json)

    # 3. Save to File: [signature(64)][payload]
    with open(output_file, "wb") as f:
        f.write(signature)
        f.write(payload_json)

    print(f"--- LICENSE GENERATED ---")
    print(f"User: {user_name}")
    print(f"Expiry: {expiry_date}")
    print(f"File saved to: {output_file}")
    print(f"-------------------------")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ripen License Generator")
    parser.add_argument("--key", required=True, help="Base64 encoded Private Key")
    parser.add_argument("--user", required=True, help="User name or email")
    parser.add_argument("--days", type=int, default=365, help="Validity period in days")
    parser.add_argument("--out", default="license.rpn", help="Output filename")

    args = parser.parse_args()
    generate_license(args.key, args.user, args.days, args.out)
