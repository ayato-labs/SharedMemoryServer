# Licensing Implementation Detail (Developer Guide)

このドキュメントは、Ripenのライセンス管理システムのソースコードレベルの詳細を記述します。

## ソースコード構成

- `src/ripen/api/licensing.py`: ライセンス管理のコアロジック（`LicenseManager` クラス）。
- `src/ripen/api/server.py`: CLI引数（`--activate`）とサーバー起動時のガード。
- `src/ripen/common/config.py`: KeygenのアカウントID、公開鍵の保持。

## 検証ロジックの要点

### 1. HTTP Signing Stringの復元
Keygenからの署名を検証するため、以下の形式で署名対象文字列（Signing String）を再構築します。

```python
signing_string = (
    f"(request-target): post {ctx['path']}\n"
    f"host: {ctx['host']}\n"
    f"date: {ctx['date']}\n"
    f"digest: {ctx['digest']}"
)
```
※改行コードやスペース一つでも異なると検証に失敗するため、`licensing.py` の `_verify_signature` メソッドの変更には細心の注意を払ってください。

### 2. ライセンス・キャッシュの形式
`~/.ripen/license.cache` に保存されるJSONには、サーバーからのレスポンスに加え、検証に必要な `signing_context` が注入されています。

```json
{
  "data": { ... },
  "meta": {
    "signature": "...",
    "signing_context": {
      "date": "...",
      "digest": "...",
      "host": "api.keygen.sh",
      "path": "..."
    }
  }
}
```

## セキュリティ上の考慮事項

- **難読化**: 現在のPython実装ではロジックが公開されています。より高度な保護が必要な場合は、PyArmor等の難読化ツールの導入、または検証コアのRust/C++化（バイナリ配布）を検討してください。
- **公開鍵の埋め込み**: 公開鍵はソースコードに直接埋め込まれています。これを環境変数に逃がすと、悪意のあるユーザーが自分の公開鍵に差し替えて偽装レスポンスを通すことが容易になるため、バイナリへの埋め込みを推奨します。

## メンテナンス手順

### 公開鍵の更新（Key Rotation）
1. Keygenダッシュボードで新しいEd25519鍵ペアを生成。
2. `src/ripen/common/config.py` の `_keygen_public_key` を新しい公開鍵（DER Base64形式）に更新。
3. リリースノートでユーザーに再アクティベーションが必要な旨を通知。
