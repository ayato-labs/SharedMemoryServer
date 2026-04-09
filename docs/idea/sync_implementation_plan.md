# `shared-memory-admin sync` 実装計画 (Team Sync機能の追加)

## 1. 背景と目的
- **課題:** SharedMemoryServer内の独自のコンテキスト（DBのグラフ構造やMemory BankのMarkdown）が個人のローカルに閉じており、複数AI間やチーム間での「認識のズレ」が発生する（Cowareが解決している課題）。
- **目的:** Coware のような「チーム間のAIコンテキスト同期」を `shared-memory-admin sync` というCLIツールとして統合し、ローカルDB(SQLite)とMarkdown(Memory Bank)をシームレスに同期する。
- **絶対ルール遵守:** 「巨人の肩の上に乗れ」— 独自の複雑な同期サーバーやWebSocketによる通信基盤は作らない。GitやSaaSのエコシステムを「バックエンド」として搾取・活用する。

---

## 2. アプローチ比較と選定 (基盤の選定)
車輪の再開発を避けるため、同期基盤として既存の強力な仕組みを活用する3つのアプローチを検討しました。

### 案A: Git 連携による Markdown ドリブン同期 (GitOps / 最もシンプル🌟)
- **概要:** 競合が発生しやすい SQLite (バイナリ) 自体を直接同期するのではなく、`memory_bank/` 内の「Markdownファイル群」をSource of Truth（正解）とし、Gitでリモートリポジトリへ同期（Push/Pull）する。Pull後に、MarkdownからローカルSQLiteを自動再構築（Hydration）する。
- **メリット:** 
    - 既存のバージョン管理（GitHub等）に完全に乗っかるため、追加インフラやアカウント登録が一切不要。
    - コンフリクト発生時もテキストベースなので人間やAIが解決しやすい。
- **デメリット:** SQLiteとMarkdownの変換処理（Hydration）の実装が必要。

### 案B: Turso (LibSQL) を用いた SQLite エッジ同期
- **概要:** 標準SQLiteから、SQLite互換の分散DBである LibSQL (Turso) へ移行する。
- **メリット:** ローカルでSQLiteとして読み書きしつつ、バックグラウンドで自動同期される。まさに「巨人の肩」。
- **デメリット:** パッケージの移行コストがかかる。また、Markdownとの同期（Atomic Mirroring）の役割が曖昧になる可能性がある。

### 案C: Supabase 等のBaaS連携
- **概要:** Supabase の Storage API などを使い、`sync` 時にファイルをアップロード。
- **デメリット:** アカウント設定が必要で、Gitほどのバージョン管理や差分解決機能がない。

**【結論】**
「シンプルイズベスト」と「Garbage in, garbage outの防止」の思想に基づき、まずは最も堅牢で追加コストゼロの **案A (GitドリブンのMarkdown同期)** を実装計画の主軸とします。

---

## 3. `shared-memory-admin sync` の動作フロー

### コマンド体系
```bash
# 基本的な同期 (内部で Pull -> Hydrate -> Commit -> Push を実行)
shared-memory-admin sync

# (初回のみ) Gitリモートの設定と初期化
shared-memory-admin sync init --remote https://github.com/your-org/memory-repo.git
```

### ステップ詳細

**Step 1. Pull (他者の知識を取り込む)**
1. ローカルの `.shared_memory` フォルダ下で `git pull origin main` を自動実行。
2. 他エージェントが更新した最新の Markdown ファイルが降ってくる。

**Step 2. Hydrate (ローカルSQLiteの再構築)**
1. ローカルの SQLite と Pull してきた Markdown の「更新日時やハッシュ」を比較。
2. 差分がある Markdown ファイルをパースし、DB上の Knowledge Graph, Entity, Importance を安全に Upsert（上書き・追加）する。
3. （既存の `shared-memory-admin repair` ロジックを流用・洗練させる）。

**Step 3. Push (自分の知識を共有する)**
1. 自分が直近で `save_memory` した結果によって変更された Markdown ファイルを `git add` & `git commit`。
2. `git push origin main` でリモートへ反映。

---

## 4. アーキテクチャと実装ステップ

### Phase 1: Sync プロバイダーの抽象化
- `src/shared_memory/sync/` ディレクトリを新設。
- 将来的な基盤変更（Git -> Tursoなど）を見据え、`SyncProviderBase` クラスを作成。
- 実装として `GitSyncProvider` を作成。内部では標準ライブラリの `subprocess` を用いてシンプルに git コマンドを叩く。（複雑なライブラリは避け、シンプルイズベストを貫く）。

### Phase 2: CLI コマンドの統合
- `src/shared_memory/cli/admin.py` に `sync` サブコマンドを追加。
- 実行時の出力を丁寧にし、「現在何件の知識を受信し、DBに反映したか」を可視化する。

### Phase 3: Hydration (再構築) アルゴリズムの堅牢化
- 「Garbage in, garbage out」を防ぐため、PullしてきたMarkdownが不正なフォーマットだった場合は、DBの破壊を防ぐためそのファイルのUpsertをスキップ（またはエラーログを残して中断）する「パースバリデーション」を挟む。
- 更新が競合した場合、Gitレベルで競合解決させるか、同期時に LWW (Last Write Wins) を採用する。

---

## 5. 運用上の留意点（ユーザールールに基づく）
- **環境管理:** 依存パッケージ（もしGit関連のラッパーを入れる場合）は `uv pip install -e .` を介して厳格に管理する。
- **自動修正の禁止:** Ruffなどの `--fix` 機能には依存せず、Syncロジック自体が最初から整理されたコードとして記述されるようにする。
- **絶対パスの禁止:** Gitリポジトリの位置やDBパスの指定には、必ず相対パス（または環境変数 `MEMORY_BANK_DIR` などによる動的解決）を使用する。
