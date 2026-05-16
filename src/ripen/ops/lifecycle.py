import asyncio
import datetime

from ripen.common.utils import get_logger
from ripen.domain.models import STALE_ACCESS_THRESHOLD

logger = get_logger("lifecycle")


async def run_maintenance_logic(uow):
    """
    Performs 'mature' SQLite maintenance: PRAGMA optimize.
    """
    logger.info("Database maintenance starting (PRAGMA optimize)...")
    try:
        await uow.management.optimize_database()

        # Maintenance for thoughts DB (cross-UoW or dedicated task)
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork(is_thoughts=True) as t_uow:
            await t_uow.management.optimize_database()

        logger.info("Database maintenance complete.")
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")


async def start_database_maintenance(interval_seconds: int = 3600):
    """
    Background loop for periodic database maintenance.
    """
    logger.info(f"Maintenance loop started (Interval: {interval_seconds}s)")
    from ripen.infra.uow import SecureWriteContext

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with SecureWriteContext() as uow:
                await run_maintenance_logic(uow)
        except asyncio.CancelledError:
            logger.info("Maintenance loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in maintenance loop: {e}")
            await asyncio.sleep(60)


async def manage_knowledge_activation_logic(ids: list[str], status: str, uow):
    """
    Toggles the activation status of entities, relations, observations, and bank files.
    """
    if status not in ["active", "inactive", "archived"]:
        return f"Error: Invalid status '{status}'. Must be active, inactive, or archived."

    try:
        changes = 0

        # Entities
        changes += await uow.entities.update_status(ids, status)

        # Bank Files
        changes += await uow.bank.update_status(ids, status)

        # Observations (by id or by entity name)
        changes += await uow.observations.update_status_by_entities(ids, status)

        # Relations (by id or by entity name)
        changes += await uow.relations.update_status_by_entities(ids, status)

        return f"Success: Updated {changes} items across core tables to status '{status}'."
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        return f"Error: Failed to update status: {e}"


async def list_inactive_knowledge_logic(uow):
    """
    Lists all knowledge assets that are NOT active.
    """
    results = {
        "entities": await uow.entities.get_inactive_entities(),
        "relations": await uow.relations.get_inactive_relations(),
        "observations": await uow.observations.get_inactive_observations(),
        "bank_files": await uow.bank.get_inactive_bank_files(),
    }
    return results


async def run_knowledge_gc_logic(uow, age_days: int = 180, dry_run: bool = False):
    """
    Automated Garbage Collection: Move stale active knowledge to inactive.
    """
    try:
        # Business Rule: Define what 'stale' means in terms of date and access count
        before_date = (
            datetime.datetime.now() - datetime.timedelta(days=age_days)
        ).isoformat()

        stale_ids = await uow.management.get_low_activity_ids(
            before_date=before_date, max_access_count=STALE_ACCESS_THRESHOLD
        )

        if not stale_ids:
            return "No stale knowledge found for GC."

        if dry_run:
            return (
                f"Dry Run: Found {len(stale_ids)} items as candidates "
                f"for deactivation: {stale_ids[:5]}..."
            )

        res = await manage_knowledge_activation_logic(stale_ids, "inactive", uow)
        return f"GC Complete: {res}"
    except Exception as e:
        logger.error(f"GC failed: {e}")
        return f"Error: GC failed: {e}"
