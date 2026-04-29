import os

import pytest

from shared_memory.common.utils import get_bank_dir
from shared_memory.core.bank import read_bank_data, save_bank_files
from shared_memory.infra.database import async_get_connection, init_db


@pytest.mark.asyncio
async def test_bank_save_and_read():
    """Verify saving to and reading from the memory bank."""
    await init_db(force=True)
    filename = "test_node.md"
    content = "# Test Node\nThis is a test."
    agent_id = "test_agent"

    async with await async_get_connection() as conn:
        # Save
        await save_bank_files({filename: content}, agent_id, conn)

    # Read
    data = await read_bank_data()
    assert filename in data
    assert data[filename] == content

    # Verify file exists
    bank_path = os.path.join(get_bank_dir(), filename)
    assert os.path.exists(bank_path)


@pytest.mark.asyncio
async def test_bank_status_check():
    """Verify that only active files are read."""
    await init_db(force=True)
    filename = "inactive.md"
    content = "I am inactive"
    agent_id = "test_agent"

    async with await async_get_connection() as conn:
        await save_bank_files({filename: content}, agent_id, conn)

    # Deactivate
    from shared_memory.ops.lifecycle import manage_knowledge_activation_logic

    await manage_knowledge_activation_logic([filename], "inactive")

    # Read should not find it
    data = await read_bank_data()
    assert filename not in data
