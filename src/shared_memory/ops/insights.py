from shared_memory.infra.database import async_get_connection


class InsightEngine:
    @staticmethod
    async def get_summary_metrics():
        \"\"\"Aggregates high-level metrics for reporting.\"\"\"
        async with async_get_connection() as conn:
            cursor = await conn.cursor()
            metrics = {}

            # 1. Total Knowledge Units
            await cursor.execute(\"SELECT COUNT(*) FROM entities\")
            metrics[\"total_entities\"] = (await cursor.fetchone())[0]

            await cursor.execute(\"SELECT COUNT(*) FROM graph\")
            metrics[\"total_relations\"] = (await cursor.fetchone())[0]

            await cursor.execute(\"SELECT COUNT(*) FROM bank_files\")
            metrics[\"total_bank_files\"] = (await cursor.fetchone())[0]

            # 2. Activity Metrics
            await cursor.execute(\"SELECT SUM(access_count) FROM knowledge_metadata\")
            metrics[\"total_accesses\"] = (await cursor.fetchone())[0] or 0

            return metrics

    @staticmethod
    def generate_report_markdown(metrics: dict) -> str:
        \"\"\"Generates a human-readable markdown report from metrics.\"\"\"
        report = \"# SharedMemoryServer Knowledge Report\\n\\n\"
        report += \"## Inventory Summary\\n\"
        report += f\"- **Total Entities:** {metrics['total_entities']}\\n\"
        report += f\"- **Total Relations:** {metrics['total_relations']}\\n\"
        report += f\"- **Total Bank Files:** {metrics['total_bank_files']}\\n\\n\"
        report += \"## Activity Summary\\n\"
        report += f\"- **Total Knowledge Accesses:** {metrics['total_accesses']}\\n\"
        return report
