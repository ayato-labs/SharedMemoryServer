# Ripen: The "Trust Layer" for Multi-Agent AI Teams 🧠

**Centralized Knowledge Hub for AI-Driven Development. Designed for Local and Small-Team workflows.**

[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Beta-orange)](CHANGELOG.md)
[![Download Official Binary](https://img.shields.io/badge/Download-Official%20ripen.exe-brightgreen?style=for-the-badge&logo=github)](https://github.com/ayato-labs/ripen/releases)

> [!IMPORTANT]
> **Official Distribution**: Always download the hub and admin binaries from the [Official GitHub Releases](https://github.com/ayato-labs/ripen/releases). This ensures you have the latest signed binary with all security patches.

> [!NOTE]
> **Distribution Policy**: To concentrate our development resources and provide the best zero-friction experience, we focus solely on distributing standalone `.exe` files via GitHub Releases. PyPI distribution has been discontinued.

> [!TIP]
> **🚀 Special Campaign: 180-Day Free Professional License!**
> To celebrate our launch, we are distributing **180-Day Professional Licenses for FREE**!
> **Features**: Unlimited sync, commercial rights, and priority updates.
> **How to Apply**: Open a [GitHub Issue](https://github.com/ayato-labs/ripen/issues/new?title=Request+Pro+License) or email [cwblog69@gmail.com](mailto:cwblog69@gmail.com).
> **Activation**: `ripen-admin.exe license activate ./license.rpn`

> 🇯🇵 **Claude Code・Cursor・Antigravity・Gemini CLI——違うアカウントを使った別の人のPCで稼働するAIエージェントとの間でも、知識を共有できる。これが Ripen の根本的な価値です。**

---

## What Makes Ripen Different

Most MCP memory servers run in `stdio` mode — a 1:1 connection between **one IDE and one server**. Knowledge stays siloed inside that single process, invisible to any other tool or person.

**Ripen runs as a Streamable HTTP Hub** — an HTTP server that accepts **N:1 connections**. Multiple agents, multiple IDEs, multiple teammates on **different machines with different accounts**, all reading and writing to the same shared brain simultaneously.

> **Note on Scale**: Ripen is currently optimized for **local multi-agent usage or small teams (2-3 people)**. It uses SQLite + WAL mode under the hood, which provides excellent local concurrency but is not designed for high-throughput network writes from large distributed teams.

> **Privacy Warning**: Ripen uses background processes (`incremental_distill_knowledge`) to organize memory. **If you configure an external LLM (like Gemini or OpenAI), snippets of your codebase and prompts may be sent to these external APIs.** For strict enterprise environments, we strongly recommend using a local LLM via Ollama.

```text
[Typical MCP Memory]                    [Ripen Hub Mode]

Dev A: Cursor   -- memory-A             Dev A: Cursor     ----+
Dev A: Claude   -- memory-B             Dev A: Antigravity ---+
                                        Dev B: Windsurf    ---+--> Ripen HTTP Hub
Dev B: Cursor   -- memory-C             Dev B: Gemini CLI  ---+
                                        CI Agent -------------+
  No shared knowledge                   Zero manual sync
```

This is the **core innovation**: automated cross-agent, cross-user, cross-machine knowledge sharing via a local Streamable HTTP server.

---

## Quick Start

Ripen operates purely as a centralized Hub. You host it once, and all your agents connect to it.

### 1. Start the Hub
1. Download `ripen-hub.exe` and `ripen-admin.exe` from the latest release.
2. Set the `GOOGLE_API_KEY` (or other provider keys) in the environment variables on the machine running the Hub. **Clients do not need to hold any API keys.**
3. Run `ripen-hub.exe`. It will start the Streamable HTTP server on port `8377`.

### 2. Connect Your Agents
Configure your AI agents to connect to the Hub's MCP endpoint: `http://localhost:8377/mcp` (or replace `localhost` with the Hub machine's IP address for team use).

*   **For Cursor / Windsurf (Native Streamable HTTP)**:
    *   Add an MCP server of type `sse` (many tools still use the label "SSE" to refer to Streamable HTTP).
    *   URL: `http://localhost:8377/mcp`
*   **For Stdio-only Agents (Claude Code, Gemini CLI)**:
    *   Since Ripen is an HTTP Hub, standard bridging utilities (like `mcp-remote`) should be used in your configuration to connect your stdio-based agent to the Ripen HTTP endpoint.

---

## The Problem: AI "Multi-Personality Disorder"

AI-driven development made your team 10x faster, but your knowledge is now scattered:

- **Isolated Context**: Cursor knows your coding conventions — but **Claude Code doesn't**.
- **Memory Decay**: Gemini CLI resolved a bug yesterday — but **Cursor forgot it by today**.
- **Architectural Drift**: Your team decided on a pattern — but **every AI tool proposes a different one**.
- **Cross-User Silos**: Developer A's AI made a key decision — but **Developer B's AI has no idea**.

The faster you ship, the faster your AI tools **diverge**. Ripen stops this drift with a **Single Source of Truth (SSoT)** shared by every agent on your team.

---

## Architecture: Pure Hub Model

Ripen provides a unified HTTP Hub endpoint. No proprietary client proxies are needed.

```mermaid
graph TD
    subgraph "Parent PC (The Hub)"
        H["🧠 Ripen Streamable HTTP Hub\n(port 8377)"]
        H --> DB["SQLite + FAISS\n(local, private)"]
        H --> DASH["Dashboard\nlocalhost:8377/dashboard"]
    end

    subgraph "Child PC (Team Member A)"
        A1["Cursor (Streamable HTTP)"] -- "Direct HTTP" --> H
    end

    subgraph "Child PC (Team Member B)"
        B1["Claude Code (Stdio)"] -- "Standard Bridge (e.g. mcp-remote)" --> H
    end
```

---

## Key Features

### 1. Hybrid Intelligence Store
- **Logic Graph**: Stores entities and relations (e.g., *"AuthModule depends on UserService"*).
- **Memory Bank**: Stores deep context as Markdown (specs, blueprints, post-mortems).
- **Thought Log**: Captures the *reasoning process* behind decisions, not just the output.

### 2. Knowledge Lifecycle (The "Ripening" Process)
- **Maturation**: Frequently accessed knowledge is automatically "ripened" into stable long-term assets.
- **Decay & GC**: Stale or transient noise is automatically archived to keep context high-signal.

### 3. Zero-Config by Design
- LLM not configured? Core search, graph, and Memory Bank still work fully.
- Config priority: `Environment Variable` > `~/.ripen/config.json` > Defaults.
- Hub startup prints a summary of active services and the connection URL.

### 4. Professional CLI
| Command | Role |
|---------|------|
| `ripen-hub.exe` | Start the main Streamable HTTP server |
| `ripen-admin.exe` | Knowledge maintenance, GC, and license management |

### 5. Observability Dashboard
Visit `http://localhost:8377/dashboard` to see:
- **Active Agents**: Which IDEs/tools are currently connected
- **Knowledge Flow**: Real-time activity timeline
- **Hub Status**: Real-time status of AI Brain (LLM) and Memory Bank (Vector DB)

### 6. Reliability & Health Monitoring (Plan A Strategy)
Ripen prioritizes **system stability** over massive internal dependencies.
- **Proactive Health Checks**: The Hub automatically detects if Ollama or Gemini are available.
- **Zero-Crash Lifespan**: Instead of failing silently or crashing during heavy inference, Ripen provides clear visual warnings in the Dashboard and CLI if a backend is missing.
- **Dependency-Clean**: By leveraging FastEmbed for retrieval and "Bringing Your Own LLM" for reasoning, we ensure the Hub remains lightweight enough to run in the background of any 16GB RAM development machine.

---

## Benchmarks: LongMemEval

| Metric | Local (FastEmbed + Ollama) | Cloud (Gemini 2.0 Flash) |
| :--- | :---: | :---: |
| **Search Latency** | **12ms** | 420ms |
| **Context Recall (RAGAS)** | **0.95** | 0.96 |
| **Independence** | **100% Local** | Cloud Dependency |

---

## Installation

### Option A: Native Binary (Easiest for Windows) 🚀
No Python required. Best for a quick, stable setup.
1. Download `ripen-hub.exe` and `ripen-admin.exe` from [GitHub Releases](https://github.com/ayato-labs/ripen/releases).
2. Run `ripen-hub.exe` to start the server.

### Option B: Python (Source)
```bash
uv run -m src.ripen.api.server
```

---

## 🇯🇵 日本語

### 他のMCPメモリサーバーとの根本的な違い
Ripen は「1対1」ではなく「N対1」の接続を前提とした**ナレッジ・ハブ**です。
*   **従来**: 1つのIDEごとに独立したメモリ（知識が分散する）。
*   **Ripen**: 全員が1つの「共有ブレイン」に接続（知識がリアルタイムで同期する）。

---

### 🌐 チーム開発：メンバーの接続手順

管理者が構築した共有ハブに接続するためのガイドです。

#### 1. 準備
管理者から親機の URL （例: `http://192.168.1.50:8377/mcp`）を共有してもらいます。

#### 2. 接続設定
各 AI ツールに、以下の設定を入力します。

**A. Cursor / Windsurf の場合**
一番シンプルで高速な接続方法です。
1.  Cursor の MCP 設定を開く。
2.  `Type` を **SSE** (Streamable HTTPと同義) に変更。
3.  `URL` に `http://[親機のIP]:8377/mcp` を入力。

**B. Stdio専用のエージェント（Claude Code等）の場合**
汎用的なブリッジツール（`mcp-remote`等）を「翻訳機」として使います。
`mcp_config.json` 等に以下のように記述してください：
```json
"ripen": {
  "command": "npx",
  "args": ["-y", "@sammacbeth/mcp-remote", "http://[親機のIP]:8377/mcp"]
}
```

#### 3. 動作確認
エージェントに「このプロジェクトの規約を教えて」と聞いてみてください。親機に蓄積された知識を答えられれば成功です！

---

一般的なMCPメモリサーバーは `stdio` モードで動作し、**1つのIDEと1つのサーバー**が1:1で接続されます。知識はそのIDEのプロセス内に閉じており、他のツールや他のユーザーからは参照できません。

**Ripenは `Streamable HTTP Hub` として動作します。** HTTPサーバーとして常駐し、複数のIDE・複数のメンバーが同時に読み書きできます。

> **最大のポイント**: Claude Code・Cursor・Antigravity・Gemini CLI の間で知識を共有できます。しかも、**違うアカウントを使った別の人のPCで稼働するAIエージェントとの間でも。**
>
> これは「便利な追加機能」ではなく、エージェントフレームワークが構造的に実現不可能な**唯一の機能**です。

詳細は [概念的要件定義書](docs/概念的要件定義書.md) · [アーキテクチャ](docs/アーキテクチャ.md) をご覧ください。

---

## Data Governance & Privacy 🛡️

Your knowledge is your most valuable asset. Ripen is designed to give you full control over it:

- **Local-First**: All data is stored on your machine in a single SQLite database.
- **Data Location**: By default, everything lives in `~/.ripen/` (Windows: `C:\Users\<User>\.ripen`).
- **Portability**: To backup or migrate, simply copy the `~/.ripen/knowledge.db` file.

---

## Donations & Support ☕

開発者への寄付やサポートをご検討いただける場合、以下のサービスをご利用いただけます。
日本在住のため Stripe や GitHub Sponsors が利用できないため、**OFUSE (オフセ)** を通じてご支援いただければ幸いです。

👉 **[OFUSE で Ripen を支援する](https://ofuse.me/21cfc1d2)**

---

## License

- **Open Source**: [AGPL-3.0](LICENSE) — free for personal and open-source use.
- **Commercial**: For proprietary team integrations, a [Commercial License](COMMERCIAL.md) is available. 
  - **180-day (6-month) free trial** is standard for all teams.
  - **Special Campaign**: Currently, 180-day Professional Licenses are being distributed for **FREE**. 
  - **Why Free?**: Ripen is open-sourced under AGPL-3.0. We have implemented a strict licensing model specifically to prevent unauthorized "copy-and-sell" practices by third parties while ensuring the community and developers can use it safely and freely.

*Ripen: Making AI agents remember what your team already decided.*
