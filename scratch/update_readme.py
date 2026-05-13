import os

readme_path = r"c:\Users\saiha\My_Service\programing\MCP\Ripen\Ripen-free\README.md"

with open(readme_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_quick_start = """## Quick Start: Two Setup Patterns

Ripen supports two primary workflows. Choose the one that fits your team structure:

### 🏠 Pattern A: Personal Hub (Single User, Multiple Agents)
Use this if you are a solo developer using multiple tools (Cursor + Gemini CLI + Claude) on one machine.

1.  **Start Hub**: Run `bin/sse.bat` and select `[1] Local Only`.
2.  **Connect Agents**:
    *   **Cursor**: Add MCP server `http://localhost:8377/sse` (Type: SSE).
    *   **CLI Tools**: Use the standard `ripen --stdio` proxy in your config.

### 🌐 Pattern B: Team Hub (Shared Brain for the Team)
Use this if you want to share knowledge across different people and different machines.

1.  **Start Hub (Parent PC)**: Run `bin/sse.bat` and select `[2] Team/Public`.
2.  **Distribute Client (To Teammates)**:
    *   Run `scripts/build_client.bat` to generate `dist/client/ripen-client.exe`.
    *   Send this EXE to your teammates.
3.  **Connect (Child PCs)**:
    *   Teammates run `bin/connect_to_hub.bat` and enter your Parent PC's IP address.
    *   Their AI agents now read and write to your shared knowledge base.

---
"""

new_architecture = """## Architecture: Hub & Spokes

```mermaid
graph TD
    subgraph "Parent PC (The Hub)"
        H["🧠 Ripen SSE Server\\n(port 8377)"]
        H --> DB["SQLite + FAISS\\n(local, private)"]
        H --> DASH["Dashboard\\nlocalhost:8377/dashboard"]
    end

    subgraph "Child PC (Team Member A)"
        A1["Cursor (SSE Native)"] -- "Direct HTTP" --> H
        A2["Gemini CLI (Stdio)"] -- "Stdio" --> P1["ripen-client.exe"]
        P1 -- "Bridge" --> H
    end

    subgraph "Child PC (Team Member B)"
        B1["Claude Code (Stdio)"] -- "Stdio" --> P2["ripen-client.exe"]
        P2 -- "Bridge" --> H
    end
```

### Which role should I take?

| Role | Responsibility | Requirement |
| :--- | :--- | :--- |
| **Parent (Hub)** | Hosts the knowledge base and runs background distillation. | Full Python environment, LLM API Key, keeps `sse.bat` running. |
| **Child (Spoke)** | Connects to the Hub to read/write knowledge. | **Zero Install.** Just needs `ripen-client.exe` and the Parent's IP. |

---

## Team Deployment Guide

### 1. Preparing the Hub (Parent)
On the computer that will host the memory (can be a server or a leader's workstation):
1.  Ensure you have Python 3.10+ and `uv` installed.
2.  Run `bin/sse.bat`.
3.  Choose **Option [2] Team/Public**.
4.  **Important**: Note your IP address (run `ipconfig` to find it). Ensure your Firewall allows inbound traffic on port `8377`.

### 2. Distributing the Connector
You don't need to share your whole source code or credentials.
1.  Run `scripts/build_client.bat`.
2.  This generates a single, lightweight binary: `dist/client/ripen-client.exe`.
3.  Share this EXE with your teammates via Slack, Discord, or shared drive.

### 3. Connecting Teammates (Child)
On the teammate's machine:
1.  Place `ripen-client.exe` in a stable folder.
2.  Run `bin/connect_to_hub.bat`.
3.  Enter the Parent's IP (e.g., `http://192.168.1.50:8377`).
4.  **Done.** Their AI agents are now synchronized with yours.

> [!WARNING]
> **Data Privacy**: Teammates connecting to your Hub will be able to read all knowledge currently in the Hub. Use this for trusted team collaborations only. For isolation, use separate data directories via the `--data-dir` flag.

---
"""

# Replace lines 49 to 79 (indices 48 to 79)
# Note: lines[78] is "---"
lines[48:79] = [new_quick_start]

# Now we need to find the new indices for Architecture
# Re-scan for "## Architecture: Hub & Clients"
for i, line in enumerate(lines):
    if "## Architecture: Hub & Clients" in line:
        arch_start = i
        break
else:
    # Fallback to searching for mermaid if title changed or not found
    for i, line in enumerate(lines):
        if "```mermaid" in line and i > 50:
            arch_start = i - 1
            break

# Find end of mermaid
arch_end = arch_start
for i in range(arch_start + 1, len(lines)):
    if "```" in lines[i]:
        arch_end = i + 1
        # Check if there is more text like "One Hub. N Clients." that we want to replace
        if i + 2 < len(lines) and "One Hub. N Clients." in lines[i+2]:
            arch_end = i + 4
        break

lines[arch_start:arch_end] = [new_architecture]

with open(readme_path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("README.md updated successfully via Python script.")
