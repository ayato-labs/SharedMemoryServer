import asyncio
import time
import json
import os
import sys
import re
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from shared_memory.core.search import perform_search, perform_keyword_search
from shared_memory.infra.database import init_db, async_get_connection
from shared_memory.infra.embeddings import compute_embedding
from shared_memory.common.utils import batch_cosine_similarity

# --- ターゲットキーワード (トラブルシューティング用) ---
PRIORITY_KEYWORDS = ["error", "bug", "fail", "trouble", "issue", "locked", "exception", "失敗", "エラー", "バグ", "不具合"]

async def setup_mock_data():
    """検証用のトラブルシューティングデータをDBに挿入"""
    async with await async_get_connection() as conn:
        # テスト用データの挿入 (既存チェックなしで上書き気味に)
        test_data = [
            ("SQLite_Locked_Fix", "entity", "SQLite 'database is locked' errors occur when multiple processes write simultaneously. Fix by using WAL mode and retry logic."),
            ("Gemini_Quota_Issue", "entity", "Gemini API failure with 429 error is caused by quota limits. Implement AIRateLimiter to throttle requests."),
            ("Circular_Import_Bug", "entity", "Syntax error or Import error in server.py is often due to circular imports between server and logic modules."),
        ]
        
        for name, type, desc in test_data:
            await conn.execute(
                "INSERT OR REPLACE INTO entities (name, entity_type, description, status) VALUES (?, ?, ?, 'active')",
                (name, type, desc)
            )
            # 埋め込みも作成しておく（検索でヒットさせるため）
            vec = await compute_embedding(desc)
            if vec:
                await conn.execute(
                    "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                    (name, json.dumps(vec), "models/gemini-embedding-001")
                )
        await conn.commit()
        print("Mock troubleshooting data initialized.")

async def search_with_priority_boost(query: str, threshold: float = 0.65):
    """
    提案された 'Priority Boost' ロジックの実装
    """
    start = time.perf_counter()
    
    # 1. 通常のハイブリッド検索を並列で開始
    normal_search_task = asyncio.create_task(perform_search(query, candidate_limit=10))
    
    # 2. キーワード検知
    detected_keywords = [w for w in PRIORITY_KEYWORDS if w.lower() in query.lower()]
    boosted_results = []
    
    if detected_keywords:
        print(f"   [PriorityBoost] Keywords detected: {detected_keywords}")
        # キーワード検索を実行
        keyword_hits = await perform_keyword_search(query, limit=3)
        
        if keyword_hits:
            # ヒットしたものの類似度を検証
            async with await async_get_connection() as conn:
                query_vec = await compute_embedding(query)
                for hit in keyword_hits:
                    # 埋め込みを取得して類似度計算
                    cursor = await conn.execute("SELECT vector FROM embeddings WHERE content_id = ?", (hit["id"],))
                    row = await cursor.fetchone()
                    if row:
                        hit_vec = json.loads(row[0])
                        sim = batch_cosine_similarity(query_vec, [hit_vec])[0]
                        
                        if sim >= threshold:
                            print(f"   [PriorityBoost] Boosting '{hit['id']}' (Similarity: {sim:.3f} >= {threshold})")
                            boosted_results.append({
                                "id": hit["id"],
                                "content": hit["content"],
                                "score": sim,
                                "boosted": True
                            })

    # 3. 通常結果を待機
    graph_data, bank_data = await normal_search_task
    
    # 4. マージロジック
    final_results = []
    seen_ids = set()
    
    # まずブーストされたものを最上位に
    for r in boosted_results:
        final_results.append(r)
        seen_ids.add(r["id"])
    
    # 残りを通常結果から補充
    for ent in graph_data.get("entities", []):
        if ent["name"] not in seen_ids:
            final_results.append({"id": ent["name"], "content": ent["description"], "boosted": False})
            seen_ids.add(ent["name"])
    
    for filename, content in bank_data.items():
        if filename not in seen_ids:
            final_results.append({"id": filename, "content": content[:200], "boosted": False})
            seen_ids.add(filename)

    dur = time.perf_counter() - start
    return final_results[:7], dur

async def run_comparison(query: str):
    print(f"\n{'='*80}")
    print(f" QUERY: '{query}'")
    print(f"{'='*80}")

    # 1. Normal Hybrid Search
    print("\n[Method A: Normal Hybrid Search]")
    start_a = time.perf_counter()
    g, b = await perform_search(query, candidate_limit=7)
    dur_a = time.perf_counter() - start_a
    
    res_a = []
    for e in g.get("entities", []): res_a.append(e["name"])
    for f in b.keys(): res_a.append(f)
    
    print(f"  Duration: {dur_a:.4f}s")
    print(f"  Top 3 Results: {res_a[:3]}")

    # 2. Priority Boost Search
    print("\n[Method B: Priority Boost Search]")
    res_b, dur_b = await search_with_priority_boost(query)
    
    print(f"  Duration: {dur_b:.4f}s")
    print(f"  Top 3 Results (IDs): {[r['id'] for r in res_b[:3]]}")
    for i, r in enumerate(res_b[:3]):
        boost_tag = "[BOOSTED]" if r.get("boosted") else ""
        print(f"     {i+1}. {boost_tag} {r['id']}")

    # 分析
    if res_a and res_b and res_a[0] != res_b[0] and res_b[0].get("boosted", False) if isinstance(res_b[0], dict) else False:
        print("\n[ANALYSIS] Priority Boost successfully elevated a critical troubleshooting item to the top.")
    elif detected := [w for w in PRIORITY_KEYWORDS if w.lower() in query.lower()]:
        print("\n[ANALYSIS] Keywords detected but no item exceeded the similarity threshold for boosting.")
    else:
        print("\n[ANALYSIS] No priority keywords in query. Method B acted as Normal Search.")

async def main():
    await init_db()
    await setup_mock_data()
    
    queries = [
        "How to handle 'database is locked' error in SQLite?",  # キーワードあり・重要
        "circular import bug in server.py",                     # キーワードあり・重要
        "Tell me about the general architecture",              # キーワードなし・通常
        "Gemini API fail due to quota",                         # キーワードあり・重要
    ]
    
    for q in queries:
        await run_comparison(q)

if __name__ == "__main__":
    asyncio.run(main())
