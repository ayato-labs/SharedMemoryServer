# SharedMemoryServer (Hybrid Memory MCP)

This MCP server provides a unified memory layer for AI agents, combining structured knowledge and project-specific context.

## Unified Memory API (V2)

The server now features a consolidated 3-tool API for maximum simplicity and efficiency:

### 1. `save_memory`
**The Entrance for Writing**. Updates both Knowledge Graph (SQLite) and Memory Bank (Markdown) in one call.
- Handles entities, relations, observations, and file updates simultaneously.

### 2. `read_memory`
**The Entrance for Reading**. Unified search and retrieval across both Graph and Bank.
- Performs hybrid retrieval based on an optional keyword query and scope.

### 3. `delete_memory`
**The Entrance for Deletion**. Targeted removal of specific entities and their related context.

## Environment Variables
- `MEMORY_DB_PATH`: Path to the SQLite database (default: `shared_memory.db`).
- `MEMORY_BANK_DIR`: Directory for memory bank markdown files (default: `memory_bank`).

## Installation & Setup

1. **Install Dependencies**:
   ```bash
   uv pip install -e .
   ```

2. **Automatic Registration**:
   Register this MCP server with your AI agents (Claude Desktop, Cursor, etc.) automatically:
   ```bash
   shared-memory-register
   ```
   *(Use `--dry-run` to preview the changes without writing to config files.)*

## Advanced Features (Phase 1: Reliability & Safety)

### 1. Atomic Mirroring (信頼性の向上)
`save_memory` は、Markdownファイルの内容を自動的に SQLite データベース内の `bank_files` テーブルにもミラーリング保存します。
- **自動復旧**: 物理ファイルが消失した場合、`read_memory` は自動的にDBから内容を補完します。
- **一括修復**: `repair_memory` ツールを実行することで、DB内のデータから物理ファイルをすべて復元できます。

### 2. Project Isolation (プロジェクトの分離)
複数のプロジェクトを並行開発する際、メモリを分離したい場合は `--isolate` フラグを使用します：
```bash
python src/shared_memory/register.py --isolate
```
- 現在のディレクトリパスに基づいて固有の ID が生成され、専用の `.db` ファイルと MCP インスタンス名が作成されます。

### 3. Clean Uninstallation (クリーンアップ)
MCPの設定削除に加え、AI指示ファイル（`GEMINI.md`, `.cursorrules`等）に注入された指示も自動で消去します：
```bash
python src/shared_memory/unregister.py
```

## Intelligence Features (Phase 2 & 3: Semantic & Lifecycle)

### 4. Semantic Search & BYOK (セマンティック検索)
Google AI Studio の `gemini-embedding-001` を統合しました。
- **意味ベースの検索**: キーワードが完全に一致しなくても、文脈上の「意味」で知識を抽出します。
- **BYOK (Bring Your Own Key)**: `register.py` 実行時に自身の API キーを入力し、プロジェクトごとの環境をセキュアに保てます。
- **ハイブリッド検索**: 高速なキーワード検索と高度なベクトル検索の結果を組み合わせた re-ranking を提供します。

### 5. Knowledge Importance & Decay (重要度と忘却)
知識の「鮮度」を管理し、AIの混乱を防ぐマネジメントシステムです。
- **Importance Score**: 参照回数と経過時間に基づく指数関数的減衰（Decay Factor）を用いて、頻繁に使われる重要な情報を優先提示します。
- **Archival Mechanism**: 長期間参照されず重要度が下がった情報を `archive_memory` ツールで自動的にアクティブな文脈から除外（忘却）できます。

### 6. Observability & Hardening (観測性と堅牢化)
システムの内部状態を透明化し、デバッグを容易にします。
- **Health Diagnostics**: `get_memory_health` ツールにより、知識の蓄積量、重要度の分布、セマンティック検索の稼働状態を診断できます。
- **Improved Logging**: 全てのエラーが標準エラー出力（stderr）に集約され、サイレントな失敗を防止しました。

## Environment Variables
- `MEMORY_DB_PATH`: Path to the SQLite database.
- `MEMORY_BANK_DIR`: Directory for memory bank markdown files.

## Design Philosophy
- **Simple is Best**: Focused tools with clear inputs/outputs.
- **GIGO Prevention**: Structured SQLite schema for knowledge, standardized Markdown for bank.
- **Resilitent by Design**: Atomic synchronization between database and file system.

## Privacy & Security (Important)
- **Local Storage**: All memory data (SQLite and Markdown) is stored locally on your machine.
- **Data Protection**: Ensure your `.gitignore` includes `*.db` to prevent accidental commits of sensitive knowledge to public repositories.

## License
Licensed under the **PolyForm Shield License 1.0.0**.

> [!NOTE]
> **ライセンスの要約**:
> *   **許可**: 個人利用、社内利用、改変、配布は自由です。
> *   **制限**: このソフトウェアをそのまま、あるいは改変して**競合するSaaSサービス（有料・無料問わず）として公開・提供すること**は制限されています。
>
> 詳細は [LICENSE](LICENSE) ファイルをご確認ください。
