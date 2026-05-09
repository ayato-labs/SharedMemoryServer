from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Router

from ripen.ops import management


async def get_dashboard_html(request):
    html_content = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ripen Dashboard | Knowledge Infrastructure</title>
    <link 
        href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=Inter:wght@300;400;600&display=swap" 
        rel="stylesheet">
    <style>
        :root {
            --bg-color: #0a0c10;
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.1);
            --accent-primary: #6366f1;
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
            letter-spacing: -0.02em;
            background: linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 999px;
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
            font-size: 0.875rem;
            font-weight: 600;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        .pulse {
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
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
            transition: all 0.3s ease;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.2);
        }

        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: var(--text-primary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
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
            padding: 1.25rem;
            border-radius: 16px;
            border: 1px solid var(--glass-border);
        }

        .time { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.5rem; }
        .action { 
            font-weight: 600; 
            color: var(--accent-secondary); 
            text-transform: uppercase; 
            font-size: 0.75rem; 
            margin-right: 0.5rem; 
        }
        .agent-name { color: var(--text-primary); font-size: 0.875rem; font-weight: 500; }

        /* Agent List */
        .agent-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .agent-pill {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 1rem;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            font-size: 0.875rem;
        }

        .agent-icon {
            width: 10px;
            height: 10px;
            background: var(--success);
            border-radius: 50%;
        }

        .empty-state { text-align: center; color: var(--text-secondary); padding: 2rem; font-size: 0.875rem; }

        @media (max-width: 900px) {
            .grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">RIPEN HUB</div>
            <div class="status-badge">
                <div class="pulse"></div>
                SYSTEM ONLINE
            </div>
        </header>

        <div class="grid">
            <main>
                <div class="card">
                    <h2 class="section-title">Knowledge Flow</h2>
                    <div id="timeline" class="timeline">
                        <div class="empty-state">Loading timeline...</div>
                    </div>
                </div>
            </main>

            <aside>
                <div class="card">
                    <h2 class="section-title">Active Agents</h2>
                    <div id="agents" class="agent-list">
                        <div class="empty-state">No active agents detected.</div>
                    </div>
                </div>

                <div class="card">
                    <h2 class="section-title">Hub Status</h2>
                    <div id="stats" style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.8;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>Role:</span>
                            <span style="color: var(--text-primary); font-weight: 600;">Central Hub</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>Transport:</span>
                            <span style="color: var(--accent-secondary);">SSE (Shared)</span>
                        </div>
                    </div>
                </div>
            </aside>
        </div>
    </div>

    <script>
        function updateDashboard() {
            fetch('api/history')
                .then(res => res.json())
                .then(data => {
                    // Update Timeline
                    const timeline = document.getElementById('timeline');
                    if (data.length === 0) {
                        timeline.innerHTML = '<div class="empty-state">No activity yet.</div>';
                    } else {
                        timeline.innerHTML = data.map(item => `
                            <div class="timeline-item">
                                <div class="time">${item.timestamp}</div>
                                <div class="timeline-content">
                                    <span class="action">${item.action}</span>
                                    <span style="font-weight: 500;">${item.cid}</span>
                                    <span class="agent-name">by ${item.agent}</span>
                                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">
                                        ${item.table}
                                    </div>
                                </div>
                            </div>
                        `).join('');
                    }

                    // Update Active Agents
                    const agentsList = document.getElementById('agents');
                    const agents = [...new Set(data.map(item => item.agent))];
                    
                    if (agents.length === 0) {
                        agentsList.innerHTML = '<div class="empty-state">No active agents.</div>';
                    } else {
                        agentsList.innerHTML = agents.map(name => `
                            <div class="agent-pill">
                                <div class="agent-icon"></div>
                                <span>${name}</span>
                                <span style="margin-left: auto; font-size: 0.7rem; color: var(--success); opacity: 0.7;">ACTIVE</span>
                            </div>
                        `).join('');
                    }
                });
        }

        updateDashboard();
        setInterval(updateDashboard, 5000);
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
        Route("/dashboard", get_dashboard_html, methods=["GET"]),
        Route("/api/history", api_history, methods=["GET"]),
        Route("/api/conflicts", api_conflicts, methods=["GET"]),
        Route("/api/conflicts/{id:int}/resolve", api_resolve_conflict, methods=["POST"]),
    ]
)
