# Database Schema Definitions
Generated at: 2026-05-06 16:15:47

This document is automatically generated from `src/ripen/schema/definitions.yaml`. Do not edit manually.

## Database: main
Ripenの主軸となる知識データベース

### Table: `entities`
知識の主体となる実体（Entity）の定義

| Column | Type/Constraints |
| :--- | :--- |
| name | `TEXT PRIMARY KEY` |
| entity_type | `TEXT` |
| description | `TEXT` |
| importance | `INTEGER DEFAULT 5` |
| created_at | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` |
| updated_at | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` |
| created_by | `TEXT` |
| updated_by | `TEXT` |
| status | `TEXT DEFAULT 'active'` |

#### Full Text Search (FTS5)
- Enabled (Automatic detection)

### Table: `relations`
実体間の関係性（Predicate）の定義

| Column | Type/Constraints |
| :--- | :--- |
| subject | `TEXT` |
| object | `TEXT` |
| predicate | `TEXT` |
| justification | `TEXT` |
| created_at | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` |
| created_by | `TEXT` |
| status | `TEXT DEFAULT 'active'` |

### Table: `observations`
実体に関する具体的な観察事項（事実）

| Column | Type/Constraints |
| :--- | :--- |
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| entity_name | `TEXT` |
| content | `TEXT` |
| timestamp | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
| created_by | `TEXT` |
| status | `TEXT DEFAULT 'active'` |

#### Full Text Search (FTS5)
- Enabled (Automatic detection)

### Table: `embedding_cache`
埋め込みベクトルのキャッシュ（同一コンテンツの再計算防止）

| Column | Type/Constraints |
| :--- | :--- |
| content_hash | `TEXT PRIMARY KEY` |
| vector | `BLOB` |
| model_name | `TEXT` |
| created_at | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` |

### Table: `bank_files`
外部知識（Bankファイル）のコンテンツと同期状態

| Column | Type/Constraints |
| :--- | :--- |
| filename | `TEXT PRIMARY KEY` |
| content | `TEXT` |
| last_synced | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
| updated_by | `TEXT` |
| status | `TEXT DEFAULT 'active'` |

#### Full Text Search (FTS5)
- Enabled (Automatic detection)

### Table: `embeddings`
知識コンテンツに紐づく埋め込みベクトル（検索用）

| Column | Type/Constraints |
| :--- | :--- |
| content_id | `TEXT PRIMARY KEY` |
| vector | `BLOB` |
| model_name | `TEXT` |
| updated_at | `DATETIME DEFAULT CURRENT_TIMESTAMP` |

### Table: `knowledge_metadata`
知識の利用統計、安定性、重要度スコア

| Column | Type/Constraints |
| :--- | :--- |
| content_id | `TEXT PRIMARY KEY` |
| access_count | `INTEGER DEFAULT 0` |
| last_accessed | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
| stability | `REAL DEFAULT 0.1` |
| importance_score | `REAL DEFAULT 0.1` |
| decay_rate | `REAL DEFAULT 0.01` |

### Table: `audit_logs`
データの変更履歴（Auditing）

| Column | Type/Constraints |
| :--- | :--- |
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| table_name | `TEXT` |
| content_id | `TEXT` |
| action | `TEXT` |
| old_data | `TEXT` |
| new_data | `TEXT` |
| timestamp | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
| agent_id | `TEXT` |
| meta_data | `TEXT` |

### Table: `conflicts`
知識の衝突（事実不一致）の検知と解決状態

| Column | Type/Constraints |
| :--- | :--- |
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| entity_name | `TEXT NOT NULL` |
| existing_content | `TEXT NOT NULL` |
| new_content | `TEXT NOT NULL` |
| reason | `TEXT` |
| agent_id | `TEXT` |
| detected_at | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
| resolved | `INTEGER DEFAULT 0` |

### Table: `search_stats`
検索クエリの統計（ヒット率、類似度平均等）

| Column | Type/Constraints |
| :--- | :--- |
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| timestamp | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
| query | `TEXT` |
| results_count | `INTEGER` |
| hit_content_ids | `TEXT` |
| avg_similarity | `REAL DEFAULT 0.0` |
| meta_data | `TEXT` |

### Table: `tags`
知識コンテンツに付与されたタグ

| Column | Type/Constraints |
| :--- | :--- |
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| tag | `TEXT NOT NULL` |
| content_id | `TEXT NOT NULL` |
| content_type | `TEXT NOT NULL` |

#### Indices
- `idx_tags_tag`: (tag)
- `idx_tags_content`: (content_id)

#### Unique Constraints
- `UNIQUE(tag, content_id, content_type)`

### Table: `troubleshooting_knowledge`
トラブルシューティング用の知見（エラーと解決策）

| Column | Type/Constraints |
| :--- | :--- |
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| title | `TEXT NOT NULL` |
| solution | `TEXT NOT NULL` |
| affected_functions | `TEXT` |
| env_metadata | `TEXT` |
| access_count | `INTEGER DEFAULT 0` |
| created_at | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
| updated_at | `DATETIME DEFAULT CURRENT_TIMESTAMP` |

## Database: thoughts
エージェントの思考プロセス（Sequential Thinking）を記録するデータベース

### Table: `thought_history`
セッションごとの思考履歴

| Column | Type/Constraints |
| :--- | :--- |
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| session_id | `TEXT NOT NULL` |
| thought_number | `INTEGER NOT NULL` |
| total_thoughts | `INTEGER NOT NULL` |
| thought | `TEXT NOT NULL` |
| next_thought_needed | `BOOLEAN` |
| is_revision | `BOOLEAN DEFAULT 0` |
| revises_thought | `INTEGER` |
| branch_from_thought | `INTEGER` |
| branch_id | `TEXT` |
| distilled | `BOOLEAN DEFAULT 0` |
| meta_data | `TEXT` |
| timestamp | `DATETIME DEFAULT CURRENT_TIMESTAMP` |

#### Indices
- `idx_thought_session`: (session_id)
- `idx_thought_number`: (session_id, thought_number)
- `idx_thought_timestamp`: (timestamp)

#### Full Text Search (FTS5)
- Enabled for: (session_id, thought_number, thought)

## Database: master
管理用データベース（各DBのステータス管理）

### Table: `databases`
管理対象のデータベース一覧

| Column | Type/Constraints |
| :--- | :--- |
| db_id | `TEXT PRIMARY KEY` |
| file_path | `TEXT NOT NULL` |
| current_version | `INTEGER DEFAULT 0` |
| status | `TEXT DEFAULT 'healthy'` |
| last_checked | `DATETIME DEFAULT CURRENT_TIMESTAMP` |
