# MCP接続エラー: EOF (Connection Closed) の解決

## 発生した問題

`SharedMemoryServer` (および `LogicHive`) をMCPサーバーとして起動した際、ツール実行時に `connection closed: EOF` エラーが発生し、通信が途絶する問題が発生しました。

### 症状
- エラーメッセージ: `Failure in MCP tool execution: connection closed: calling "tools/call": client is closing: EOF`
- ツール呼び出しの瞬間にサーバープロセスが終了する。
- 診断ログ(`server.log`)が空のまま、または初期化の途中で記録が止まっている。

## 原因分析

主な原因は **標準出力 (stdout) の汚染** です。

1. **JSON-RPCプロトコルの制約**: MCPのstdioトランスポートは `stdout` を通信に使用します。ライブラリ(`google-genai` や `numpy` 等)が初期化時に出力するバナー、アップデート通知、あるいは単純な `print` 文が `stdout` に混入すると、クライアント側でJSONパースエラーが発生します。
2. **クライアント側の切断**: パースエラーを検知したMCPクライアント(Antigravity/Cursor等)は、セキュリティと整合性のために即座にパイプを閉じます。これがサーバー側からは `EOF` として観測されます。
3. **潜在的なノイズ**: `uv run` 自体がパッケージ解決の進捗を `stdout` に出すことがあり、これも通信を阻害する要因となります。

## 解決策: 「サイレント初期化」戦略

### 1. 標準出力の完全なガード (server.py)
インポート時や初期化時の不要な出力を完全に排除するため、`server.py` の最上部で `sys.stdout` を `sys.stderr` へリダイレクトする処理を実装しました。

```python
import sys
# 本物のstdoutハンドルを保持
_REAL_STDOUT = sys.stdout
# 通信以外はすべてstderrへ送る
sys.stdout = sys.stderr

# ... インポート処理 ...

def main():
    # MCP通信の開始直前にのみstdoutを復元
    sys.stdout = _REAL_STDOUT
    mcp.run(transport="stdio")
```

### 2. 実行コマンドの直接指定 (mcp_config.json)
`uv run` 経由ではなく、仮想環境内の `python.exe` を直接呼び出す構成に変更しました。これにより、ラッパーによる不要な出力をゼロに抑えています。

```json
"SharedMemoryServer": {
  "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
  "args": ["C:\\path\\to\\src\\shared_memory\\server.py"]
}
```

### 3. ログ出力の分離
`logging.basicConfig` を使用して、アプリケーションログを `stdout` から完全に切り離し、絶対パスで指定された `server.log` ファイルへ直接出力するようにしました。

## 復旧のためのベストプラクティス

修正適用後もエラーが続く場合は、以下の手順を試してください:
1. **プロセスの強制終了**: `taskkill /F /IM python.exe /T` を実行し、残留している古いプロセスを完全に掃除します。
2. **IDEの再起動**: クライアント側の状態をリセットするため、IDE(Cursor等)を再起動してください。
3. **絶対パスの確認**: `mcp_config.json` 内のパスが正しいか、特に `PYTHONPATH` が `src` ディレクトリを正しく指しているかを確認してください。

---
*作成日: 2026-04-23*
*ステータス: 解決済み(要環境再起動)*
