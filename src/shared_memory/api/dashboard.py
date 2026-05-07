from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Router

from shared_memory.ops import management


async def get_dashboard_html(request):
    html_content = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SharedMemory Dashboard | Transparency & Trust</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0a0c10;
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.1);
            --accent-primary: #4f46e5;
            --accent-secondary: #06b6d4;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            overflow-x: hidden;
            min-height: 100vh;
            background: radial-gradient(circle at top right, #1e1b4b, transparent),
                        radial-gradient(circle at bottom left, #083344, transparent);
        }

        h1, h2, h3 { font-family: 'Outfit', sans-serif; }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 3rem;
            padding: 1.5rem;
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: 600;
            background: linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .status-badge {
            padding: 0.5rem 1rem;
            border-radius: 999px;
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
            font-size: 0.875rem;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 2rem;
        }

        .card {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            padding: 2rem;
            margin-bottom: 2rem;
            transition: transform 0.3s ease;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.2);
        }

        .section-title {
            font-size: 1.25rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .section-title::before {
            content: '';
            width: 4px;
            height: 1.25rem;
            background: var(--accent-primary);
            border-radius: 2px;
        }

        /* Timeline Styles */
        .timeline {
            position: relative;
            padding-left: 2rem;
        }

        .timeline::before {
            content: '';
            position: absolute;
            left: 0.5rem;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--glass-border);
        }

        .timeline-item {
            position: relative;
            margin-bottom: 2rem;
        }

        .timeline-item::after {
            content: '';
            position: absolute;
            left: -1.75rem;
            top: 0.5rem;
            width: 12px;
            height: 12px;
            background: var(--accent-primary);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-primary);
        }

        .timeline-content {
            background: rgba(255, 255, 255, 0.02);
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid var(--glass-border);
        }

        .time { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.5rem; }
        .action { font-weight: 600; color: var(--accent-secondary); text-transform: uppercase; font-size: 0.75rem; margin-right: 0.5rem; }
        .agent-name { color: var(--text-secondary); font-size: 0.875rem; }

        /* Conflict Items */
        .conflict-item {
            background: rgba(245, 158, 11, 0.05);
            border: 1px solid rgba(245, 158, 11, 0.2);
            border-radius: 16px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }

        .conflict-meta { font-size: 0.875rem; margin-bottom: 1rem; display: flex; justify-content: space-between; }
        .conflict-reason { color: var(--warning); font-size: 0.875rem; margin-bottom: 1rem; font-style: italic; }

        .diff-container {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .diff-box {
            padding: 0.75rem;
            border-radius: 8px;
            font-size: 0.875rem;
            overflow-x: auto;
            white-space: pre-wrap;
        }

        .old { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); color: #fecaca; }
        .new { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); color: #a7f3d0; }

        .btn-group { display: flex; gap: 0.5rem; }
        button {
            padding: 0.5rem 1rem;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }

        .btn-approve { background: var(--success); color: white; }
        .btn-approve:hover { filter: brightness(1.1); transform: translateY(-1px); }
        .btn-reject { background: transparent; border: 1px solid var(--glass-border); color: var(--text-secondary); }
        .btn-reject:hover { background: rgba(239, 68, 68, 0.1); color: var(--danger); border-color: var(--danger); }

        .empty-state { text-align: center; color: var(--text-secondary); padding: 2rem; }

        @media (max-width: 900px) {
            .grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">SharedMemory Dashboard</div>
            <div class="status-badge">Active Systems</div>
        </header>

        <div class="grid">
            <main>
                <div class="card">
                    <h2 class="section-title">Conflict Center</h2>
                    <div id="conflicts-list">
                        <div class="empty-state">Loading pending conflicts...</div>
                    </div>
                </div>

                <div class="card">
                    <h2 class="section-title">Activity Timeline</h2>
                    <div id="timeline" class="timeline"></div>
                </div>
            </main>

            <aside>
                <div class="card">
                    <h2 class="section-title">System Insights</h2>
                    <p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.6;">
                        Trust is built through transparency. This dashboard allows you to audit the "Blackboard" of your team's AI agents.
                    </p>
                </div>
                <div class="card">
                    <h3 style="font-size: 1rem; margin-bottom: 1rem;">Stats</h3>
                    <div id="stats" style="font-size: 0.875rem; color: var(--text-secondary);">
                        Fetching metrics...
                    </div>
                </div>
            </aside>
        </div>
    </div>

    <script>
        function fetchHistory() {
            fetch('api/history')
                .then(res => res.json())
                .then(data => {
                    const timeline = document.getElementById('timeline');
                    timeline.innerHTML = data.map(item => 
                        '<div class="timeline-item">' +
                        '<div class="time">' + item.timestamp + '</div>' +
                        '<div class="timeline-content">' +
                        '<span class="action">' + item.action + '</span>' +
                        '<span style="font-weight: 500;">' + item.cid + '</span>' +
                        '<span class="agent-name">by ' + item.agent + '</span>' +
                        '<div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">Table: ' + item.table + '</div>' +
                        '</div></div>'
                    ).join('');
                });
        }

        function fetchConflicts() {
            fetch('api/conflicts')
                .then(res => res.json())
                .then(data => {
                    const list = document.getElementById('conflicts-list');
                    if (data.length === 0) {
                        list.innerHTML = '<div class="empty-state">No pending conflicts. All knowledge is synchronized.</div>';
                        return;
                    }
                    list.innerHTML = data.map(c => 
                        '<div class="conflict-item">' +
                        '<div class="conflict-meta">' +
                        '<span style="font-weight: 600;">Entity: ' + c.entity + '</span>' +
                        '<span class="agent-name">Proposed by ' + c.agent + '</span>' +
                        '</div>' +
                        '<div class="conflict-reason">Contradiction: ' + c.reason + '</div>' +
                        '<div class="diff-container">' +
                        '<div class="diff-box old"><strong>EXISTING:</strong><br>' + c.existing + '</div>' +
                        '<div class="diff-box new"><strong>PROPOSED:</strong><br>' + c.proposed + '</div>' +
                        '</div>' +
                        '<div class="btn-group">' +
                        '<button class="btn-approve" onclick="resolve(' + c.id + ', \\'approve\\')">Approve & Merge</button>' +
                        '<button class="btn-reject" onclick="resolve(' + c.id + ', \\'reject\\')">Reject</button>' +
                        '</div></div>'
                    ).join('');
                });
        }

        function resolve(id, action) {
            fetch('api/conflicts/' + id + '/resolve?action=' + action, { method: 'POST' })
                .then(res => {
                    if (res.ok) {
                        fetchConflicts();
                        fetchHistory();
                    }
                });
        }

        fetchHistory();
        fetchConflicts();
        setInterval(fetchHistory, 5000);
        setInterval(fetchConflicts, 5000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


async def api_history(request):
    limit = int(request.query_params.get("limit", 20))
    history = await management.get_audit_history_logic(limit=limit)
    return JSONResponse(history)


async def api_conflicts(request):
    conflicts = await management.get_unresolved_conflicts_logic()
    return JSONResponse(conflicts)


async def api_resolve_conflict(request):
    conflict_id = int(request.path_params.get("id"))
    action = request.query_params.get("action", "approve")
    result = await management.resolve_conflict_logic(conflict_id, action)
    return JSONResponse({"status": "success", "message": result})


router = Router(
    [
        Route("/history", get_dashboard_html, methods=["GET"]),
        Route("/api/history", api_history, methods=["GET"]),
        Route("/api/conflicts", api_conflicts, methods=["GET"]),
        Route("/api/conflicts/{id:int}/resolve", api_resolve_conflict, methods=["POST"]),
    ]
)
