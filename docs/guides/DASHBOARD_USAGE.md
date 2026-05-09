# Transparency Dashboard Usage Guide

The Ripen dashboard is a powerful tool for visualizing what AI agents are memorizing, identifying where contradictions occur, and allowing humans to maintain the final control (governance) over the shared knowledge base.

## How to Access

With the server running, open the following URL in your browser:

- **URL**: `http://localhost:8377/history`
- **Port**: Default is `8377` (can be changed using the `--port` startup option).

## Key Features

### 1. Conflict Center
When the AI detects new information that contradicts existing knowledge, it is not immediately applied. Instead, it is listed here as "Pending".

- **Existing**: Confirmed information currently stored in the primary database.
- **Proposed**: The new, contradictory information an agent attempted to save.
- **Actions**:
    - **Approve & Merge**: Validates the proposed info as "Truth" and integrates it into primary memory.
    - **Reject**: Dismisses the proposed info as an "Error" and maintains the current state.

> [!IMPORTANT]
> This Human-in-the-Loop process prevents the knowledge base from being corrupted by incorrect information or hallucinations.

### 2. Activity Timeline
Displays a complete history of when agents performed specific actions (Save, Update, etc.).

- **Action**: Type of operation (e.g., ENTITY_SAVE, OBS_SAVE).
- **ID**: The ID or CID of the targeted knowledge.
- **Agent**: Which agent (Cursor, Claude, Gemini, etc.) contributed the knowledge.

### 3. System Insights & Stats
View a summary of system health and knowledge accumulation progress.

## Team Operation Scenarios

1.  **Validating Knowledge Reliability**: When a major project policy changes and the AI detects it as a contradiction, the team leader can review and approve the new policy via the dashboard.
2.  **Ensuring Traceability**: If knowledge seems modified unexpectedly, you can trace back through the timeline to identify exactly which agent made the change and when.
3.  **AI Debugging**: If an AI is not recalling information as expected, use the dashboard to verify if the save process is working or if the knowledge is being blocked due to a conflict.

## Notes
- **Security**: The dashboard is currently designed for local environment access. If exposing it to a public network, we recommend setting up authentication via a reverse proxy.
- **Refresh**: The page auto-refreshes every 5 seconds. You can force an update by pressing F5 in your browser.
