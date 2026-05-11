import json
from datetime import datetime
from typing import Any

from ripen.common.utils import get_logger

logger = get_logger("insights")


class InsightEngine:
    """
    Ripenの価値を定量化するための計測エンジン。
    """

    @staticmethod
    async def get_summary_metrics(uow) -> dict[str, Any]:
        """
        データベースから取得した「計測事実」のみを抽出します。
        """
        # 1. 知識の構造統計 (Knowledge Structure)
        e_count = await uow.management.get_count("entities")
        r_count = await uow.management.get_count("relations")
        b_count = await uow.management.get_count("bank_files")

        # 知識密度 (Graph Density)
        density = 0
        if e_count > 1:
            max_possible_relations = e_count * (e_count - 1)
            density = round((r_count / max_possible_relations) * 100, 2)

        # 2. 活用実績 (Utilization Facts)
        access_stats = await uow.metadata.get_access_stats_summary()
        total_access = access_stats["total_access"]
        accessed_units = access_stats["accessed_units"]

        reuse_multiplier = 0.0
        if accessed_units > 0:
            reuse_multiplier = round(total_access / accessed_units, 2)

        # 3. 検索精度と「知の熟成度」 (Precision & Knowledge Age)
        search_metrics = await InsightEngine._calculate_search_metrics(uow)

        # 4. 推論ログの観測 (Reasoning Observation)
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork(is_thoughts=True) as t_uow:
            t_count = await t_uow.thoughts.get_total_thought_count()
            s_count = await t_uow.thoughts.get_total_session_count() or 1
            avg_steps = round(t_count / s_count, 1)

        return {
            "timestamp": datetime.now().isoformat(),
            "facts": {
                "stored_entities": e_count,
                "stored_relations": r_count,
                "stored_bank_files": b_count,
                "knowledge_graph_density_percent": density,
                "total_read_operations": total_access,
                "total_search_queries": search_metrics["total_searches"],
                "search_hit_rate_percent": search_metrics["hit_rate"],
                "avg_search_precision": search_metrics["avg_precision"],
                "knowledge_maturity": search_metrics["maturity"],
                "avg_thoughts_per_session": avg_steps,
            },
            "efficiency_indicators": {
                "reuse_multiplier": reuse_multiplier,
                "knowledge_availability_ratio": round(
                    (accessed_units / max(1, e_count + b_count)) * 100, 1
                ),
            },
        }

    @staticmethod
    async def _calculate_search_metrics(uow) -> dict[str, Any]:
        """Calculates search-related metrics including maturity and precision."""
        hit_rows = await uow.metadata.get_successful_search_stats()
        total_searches = await uow.metadata.get_total_search_count()

        precision_sum = 0.0
        total_hits = len(hit_rows)
        maturity = {"intra_session": 0, "short_term": 0, "long_term": 0}

        if total_hits > 0:
            for row in hit_rows:
                precision_sum += row["avg_similarity"] or 0.0
                await InsightEngine._update_maturity_stats(uow, row, maturity)

        hit_rate = round((total_hits / total_searches) * 100, 1) if total_searches > 0 else 0.0
        avg_precision = round(precision_sum / total_hits, 2) if total_hits > 0 else 0.0

        return {
            "total_searches": total_searches,
            "hit_rate": hit_rate,
            "avg_precision": avg_precision,
            "maturity": maturity,
        }

    @staticmethod
    async def _update_maturity_stats(uow, row, maturity: dict):
        """Update maturity statistics based on a search hit row."""
        try:
            hit_ids = json.loads(row["hit_content_ids"] or "[]")
            if not hit_ids:
                return

            target_id = hit_ids[0]
            created_at = await uow.management.get_creation_timestamp(target_id)
            if created_at:
                s_dt = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                c_dt = datetime.fromisoformat(created_at.replace(" ", "T").replace("Z", "+00:00"))
                age_hours = (s_dt - c_dt).total_seconds() / 3600

                if age_hours < 1:
                    maturity["intra_session"] += 1
                elif age_hours < 24:
                    maturity["short_term"] += 1
                else:
                    maturity["long_term"] += 1
        except Exception as e:
            logger.warning(f"Failed to calculate maturity for hit record: {e}")

    @staticmethod
    def generate_report_markdown(metrics_data: dict[str, Any]) -> str:
        """
        主観的な主張を排除し、観測された事実のみを報告する。
        """
        f = metrics_data["facts"]
        i = metrics_data["efficiency_indicators"]

        report = f"""# Ripen Fact Report: 知識の「熟成」と「活用」
Generated at: {metrics_data["timestamp"]}

## 1. 知識の熟成度と移転 (Knowledge Maturity & Transfer)
単なる量ではなく、過去の蓄積がいかに時間に耐えて活用されているかを示す指標です。

- **知の移転 (Cross-Time Transfer)**:
  > **長期 (24時間超)**: `{f["knowledge_maturity"]["long_term"]} hits`
  > **中期 (1〜24時間)**: `{f["knowledge_maturity"]["short_term"]} hits`
  > [!TIP]
  > 長期ヒットは、過去の経験が現在の推論を助けている「資産」としての証拠です。

- **検索精度 (Search Precision)**: `{f["avg_search_precision"]} score`
  > [!NOTE]
  > ベクトル検索の平均確信度。核心を突いた情報提供ができているかを計測します。

## 2. 検索と再利用の実績 (Utilization & Performance)
- **検索ヒット率 (Hit Rate)**: `{f["search_hit_rate_percent"]}%`
  (Total: {f["total_search_queries"]} queries)
- **活用係数 (Reuse Multiplier)**: `{i["reuse_multiplier"]}x`

## 3. 知識の蓄積状況 (Inventory Facts)
- **エンティティ数**: `{f["stored_entities"]} items`
- **知識密度 (Graph Density)**: `{f["knowledge_graph_density_percent"]}%`
- **バンクファイル数**: `{f["stored_bank_files"]} files`

## 4. 推論プロセスの観測 (Reasoning Insights)
- **1セッションあたりの平均思考手順**: `{f["avg_thoughts_per_session"]} steps`

---
**本レポートの性質について**:
提示されている数値はすべて、データベースのアクセスログおよび検索履歴から抽出された
**観測事実**です。価値の最終的な判断は、これらの実績に基づき
ユーザー自身が行うものと定義されています。
"""
        return report
