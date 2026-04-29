import pytest

from shared_memory.core import logic
from shared_memory.infra.database import init_db


@pytest.mark.asyncio
async def test_hybrid_search_integration(mock_llm):
    """
    結合テスト: Graph検索とBank検索が統合された結果を返すことを検証。
    """
    await init_db(force=True)

    # 1. Graphに保存
    await logic.save_memory_core(
        entities=[{"name": "Rust", "description": "Safe systems language"}]
    )

    # 2. Bankに保存
    from shared_memory.core.bank import save_bank_files
    from shared_memory.infra.database import async_get_connection

    async with await async_get_connection() as conn:
        await save_bank_files({"rust_notes.md": "# Rust Tips\nUse Cargo."}, "dev_agent", conn)

    # 3. 検索実行 (Rustに関する情報を一括取得)
    # read_memory_core returns {"graph": ..., "bank": ...}
    result = await logic.read_memory_core(query="Rust programming")

    # 4. 検証: 両方のソースから情報が含まれているか
    graph_data = result["graph"]
    bank_data = result["bank"]

    assert any(e["name"] == "Rust" for e in graph_data["entities"])
    assert any("Safe systems language" in e["description"] for e in graph_data["entities"])
    assert any("Use Cargo" in content for content in bank_data.values())


@pytest.mark.asyncio
async def test_search_no_results():
    """結合テスト: ヒットしない場合の挙動。"""
    await init_db(force=True)
    # For no results, it still returns empty containers
    result = await logic.read_memory_core(query="NonExistentThing")
    assert len(result["graph"]["entities"]) == 0
    assert len(result["bank"]) == 0
