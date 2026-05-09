---
title: "Cursorに教えたルール、Gemini CLIは知っていますか？ ── AI駆動開発の「多重人格障害」を治すOSSを作った"
emoji: "🧠"
type: "tech"
topics: ["mcp", "cursor", "gemini", "ai駆動開発", "oss"]
published: false
---

## はじめに：AIが速くなるほど、「知識の断絶」も加速する

AI駆動開発によって、開発速度は圧倒的に上がりました。

しかし、**速くなったことで新しい問題**が生まれています。

> Cursor で「このモジュールは非推奨」と決めた。
> 30分後、ターミナルで Gemini CLI を開いたら、そのモジュールを自信満々に使ったコードを提案してきた。

心当たりはありませんか？

さらに深刻なケースもあります。チームで複数のAIツールを分業させると、こんな現象が起きます。

> 1. **Antigravity** に「認証モジュールの設計方針を決めてもらう」
> 2. **Cursor** に「その方針に沿ってコードを実装してもらう」
> 3. **Claude Code** に「実装したコードのテストを書いてもらう」
> 4. **Gemini CLI** に「リファクタリングを依頼する」

Antigravity が決めた「JWT ではなくセッションベース認証を使う」という設計判断を、Cursor は知りません。Cursor が JWT で実装し、Claude Code はセッション前提でテストを書き、Gemini が全く別の方針でリファクタリングする。**「AIの多重人格障害」** です。

そして、これは同じ人間が使う複数のAIツール間だけの問題ではありません。

**チームのメンバー A が Cursor で下した設計判断を、メンバー B の Claude Code は知る方法がありません。** たとえそれが同じプロジェクトであっても、別々のPC・別々のアカウントで動いているAIエージェントは、互いの文脈を一切共有できないのです。

ツールが増え、アウトプットの速度が上がるほど、この「知識の断絶」は深刻化します。

---

## 1. 解決策：すべてのAIが読み書きする「黒板」を置く

この問題を解決するために、**[Ripen](https://github.com/ayato-labs/ripen)** をオープンソースで作りました。

:::message
**Ripenの核心価値**
Claude Code、Cursor、Antigravity、Gemini CLI の間で知識を共有できます。
しかも、**違うアカウントを使った、別の人のPCで稼働するAIエージェントとの間でも。**
:::

Ripenは、**AIのための共有黒板**です。チームのどこかの環境（localhost or チームサーバー）でSSEハブとして動作し、MCP経由で接続した全AIエージェントが同一の知識ベースを読み書きします。

```mermaid
graph TD
    subgraph "Developer A のPC"
        A1["🖥️ Cursor"]
        A2["🤖 Antigravity"]
    end
    subgraph "Developer B のPC（別アカウント）"
        B1["⌨️ Claude Code"]
        B2["🔧 Gemini CLI"]
    end
    subgraph "Ripen Hub（黒板）\nチームのどこかで稼働"
        M["📋 共有メモリ\n(SSE Hub, port 8377)"]
        M --> G["設計判断の記録\n(Knowledge Graph)"]
        M --> B["技術仕様書\n(Memory Bank)"]
        M --> T["思考ログ\n(Sequential Thinking)"]
    end
    A1 <-->|MCP over SSE| M
    A2 <-->|MCP over SSE| M
    B1 <-->|MCP over SSE| M
    B2 <-->|MCP over SSE| M
```

**ポイント**: MCP（Model Context Protocol）は Anthropic、Google、Cursor が採用した唯一の業界標準プロトコルです。Ripen はそのプロトコル層に存在するため、異なるメーカーのツールが、異なる会社のAPIを通じていても、同じ「黒板」を参照できます。

### どう変わるのか

**Before（Ripen なし）:**
```
# Developer A の Cursor
Cursor:     「fastembed 使うんですね、了解」

# Developer B の Claude Code（AのCursorが何を決めたか知らない）
Claude:     「sentence-transformers がおすすめです」 ← 矛盾

# 翌日の Gemini CLI
Gemini CLI: 「OpenAI Embeddings API を使いましょう」 ← さらに矛盾
```

**After（Ripen 導入後）:**
```
# Developer A の Cursor が書き込む
Cursor:     「fastembed 採用。黒板に記録しておきます」

# Developer B の Claude Code が自動参照
Claude:     「黒板を確認…fastembed 採用済みですね。それに沿って実装します」

# 別日の Gemini CLI も同じ黒板を参照
Gemini CLI: 「黒板を確認…fastembed 採用済み。そのまま使います」
```

**一度決めれば、誰のAIでも覚えている。** これが Ripen の本質です。

---

## 2. 他の MCP メモリサーバーとは何が違うのか

「それ、Mem0 や RAG で良くない？」という疑問があると思います。

| | Ripen | Mem0 (Cloud) | .cursorrules |
|:---|:---:|:---:|:---:|
| **クロスツール共有** | ✅ MCP 経由で全ツール | ❌ API 統合が必要 | ❌ Cursor 専用 |
| **構造化された知識** | ✅ Graph + Bank | △ ベクター検索のみ | ❌ 平文のみ |
| **プライバシー** | ✅ 完全ローカル | ❌ クラウド送信 | ✅ ローカル |
| **コスト** | ✅ 無料（OSS） | △ 有料プラン | ✅ 無料 |
| **知識の減衰管理** | ✅ 自動アーカイブ | ❌ | ❌ |
| **思考プロセスの記録** | ✅ Sequential Thinking | ❌ | ❌ |
| **チーム間・ユーザー間共有** | ✅ SSE Hub で N:1 接続 | ❌ | ❌ |

### 最大の差別化：「エージェントフレームワークに内包できない」唯一の機能

LangChain や CrewAI などのフレームワークが「うちにもメモリがある」と言っても、それは**そのフレームワーク内でのみ共有できる**にすぎません。

Cursor、Claude Code、Antigravity、Gemini CLI は、**互いに競合する別会社の別製品**です。これらは別々のPC・別々のアカウント・別々の会社のAPIで動作します。どのフレームワークも、これら全てのランタイムを同時に制御することは、**構造的に不可能**です。

```
[フレームワーク内包の限界]
  LangChain memory  → LangChain使用者同士でしか共有できない
  CrewAI memory     → CrewAI使用者同士でしか共有できない
  .cursorrules      → Cursor使用者だけ

[Ripenが可能にすること]
  Ripen SSE Hub → Cursor ✅ + Claude Code ✅ + Gemini CLI ✅ + Antigravity ✅
                  Developer A ✅ + Developer B ✅（別PC・別アカウントでも）
```

MCP はこれらすべてが採用した唯一の業界標準プロトコルです。Ripen はそのプロトコル層に存在するため、**ツールの壁・会社の壁・PCの壁・アカウントの壁を超えた知識共有**が技術的に可能な唯一の構造を持っています。

---

## 3. 2種類の記憶構造

単なるテキストのコピペツールではありません。このシステムは以下の2層の記憶を管理しています。

### Memory Bank（静的記憶 / 形式知）
Markdown ファイルとして保存され、AIが現在のモジュールの仕様やコーディングルールを読み込むためのドキュメント。人間が直接編集することもでき、Git で差分管理が可能です。

### Knowledge Graph（動的・関連記憶 / 暗黙知の構造化）
SQLite ベースで構築され、AI 自身が「Entities（エンティティ）」と「Relations（関係性）」を抽出して記録するグラフ型データベース。エージェントが開発を進めるにつれて、自動的に知識ネットワークが成長していきます。

---

## 4. ただの RAG じゃない。「思考（Thought）」の蒸留と自己組織化

このシステムの最大の特徴は、**「AI の思考プロセス自体を記録・蒸留する機能」**を持っていることです。

### Sequential Thinking（逐次思考）の保存
複雑な問題を解く際、AI に各思考ステップ（Thought）を独立したデータベースに記録させます。

### 思考から知識への「自動蒸留（Distillation）」
セッションが終了すると、AI は書き溜めた思考ログを振り返り、**「次回以降も使える汎用的な知識」だけを Knowledge Graph に抽出・保存**します。

つまり、あなたが Antigravity と壁打ちして解決したバグの知見は、Cursor が翌日コードを書くときに**自動的に参照できる「共有資産」**に変換されます。もう二度と「昨日の AI には説明したのに...」と嘆く必要はありません。

---

## 5. ローカルファーストの衝撃：API 待ち時間をゼロにする

| 項目 | クラウド依存 (旧構成) | ローカルファースト (Ripen) |
|:---|:---:|:---:|
| **検索レイテンシ** | ~420ms | **12ms（約35倍高速）** |
| **Context Recall (RAGAS)** | 0.96 | **0.95（高精度を維持）** |
| **データ漏洩リスク** | △ クラウド送信あり | ✅ 100% ローカル完結 |

ローカルの `FastEmbed` と `Ollama` を組み合わせることで、「AI が考える前に、記憶がそこにある」という次元のレスポンス速度を実現しています。

---

## 6. 2種類の導入体験：Hub と Client

Ripen には2つの導入モードがあります。

### 親機（Hub）側 ── チームに1人が実施

```bash
# SSE ハブとして起動（チームで共有するサーバー）
uvx ripen --sse

# 対話型ウィザードで設定 → 最後に「Client 接続 URL」が表示される
uvx ripen-init
# > モードを選択 [hub/client]: hub
```

### 子機（Client）側 ── チームの全メンバーが実施（Python 不要）

```bash
# Hub URL を入力するだけで全 IDE に自動登録
uvx ripen-init
# > モードを選択 [hub/client]: client
# > Hub URL: http://192.168.1.10:8377
# → Cursor / Claude Desktop / VS Code に自動設定完了

# または1コマンドで
uvx ripen-register --hub-url http://192.168.1.10:8377
```

LLM API キーは不要です。`FastEmbed`（ローカル軽量モデル）で動くため、**クラウド依存ゼロ**で即座に使い始められます。

---

## 7. なぜ SaaS ではなく「ローカル MCP」で作ったのか？

- **プライバシーとセキュリティ:** 会社の機密コードのコンテキストを外部 SaaS に送信したくない。データは自分の手元にある。
- **データ主権:** 知識はローカル環境にあり続け、Git で差分管理できる。ベンダーが倒れても知識は失われない。
- **ベンダーロックインの回避:** MCP というオープン標準に乗ることで、Claude Desktop でも Cursor でも Gemini CLI でも、**ツールを問わずに同じ記憶を使い回せる**。
- **ゼロコスト:** 追加の SaaS 契約は不要。SQLite と Markdown という、人類が最も信頼してきた技術スタックのみ。

---

## おわりに：「毎回プロンプトに全部書く」時代を終わらせる

AI 駆動開発の速度はこれからも上がり続けます。しかし、**速度が上がるほど「情報共有の設計」が重要になる**という逆説に、まだ多くのチームが気づいていません。

Ripen は、この問題に対する最初の体系的な回答です。

- AI ツールが入れ替わっても、**設計思想は不変**
- セッションが切れても、**文脈は消えない**
- チームメンバーが増えても、**AI が最初から空気を読める**
- **違うアカウントを使った別の人のPCで動くAIでも、同じ知識を共有できる**

Cursor、Claude Code、Antigravity、Gemini CLI — これらは互いに異なる会社のサービスで、それぞれが独立したコンテキストを持っています。エージェントフレームワークがこれらを横断して知識を共有することは、構造的に不可能です。MCPプロトコル層で動作するRipenだけが、この壁を超えられます。

---

**GitHub（無料・OSS）:**
https://github.com/ayato-labs/ripen

**ライセンス:** AGPL-3.0（個人・OSS 利用は無料）/ 商用ライセンスあり

ぜひ ⭐ Star をいただけると励みになります。Issue / PR も歓迎しています。
