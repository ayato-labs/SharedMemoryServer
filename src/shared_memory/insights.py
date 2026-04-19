from datetime import datetime
from typing import Any

from shared_memory.database import (
    async_get_connection,
    async_get_thoughts_connection,
    init_db,
    retry_on_db_lock,
)
from shared_memory.thought_logic import init_thoughts_db
from shared_memory.utils import get_logger

logger = get_logger("insights")


class InsightEngine:
    """
    SharedMemoryServerの価値を定量化するための計測エンジン。
    客観的な「観測可能データ」のみに基づき、事実としての実績レポートを生成します。
    """

    @staticmethod
    @retry_on_db_lock()
    async def get_summary_metrics() -> dict[str, Any]:
        """
        データベースから取得した「計測事実」のみを抽出します。
        """
        # Ensure databases are initialized
        await init_db()
        await init_thoughts_db()

        async with await async_get_connection() as conn:
            # 1. 知識の構造統計 (Knowledge Structure)
            cursor = await conn.execute("SELECT COUNT(*) FROM entities")
            e_count = (await cursor.fetchone())[0]
            cursor = await conn.execute("SELECT COUNT(*) FROM relations")
            r_count = (await cursor.fetchone())[0]
            cursor = await conn.execute("SELECT COUNT(*) FROM bank_files")
            b_count = (await cursor.fetchone())[0]

            # 知識密度 (Graph Density)
            density = 0
            if e_count > 1:
                max_possible_relations = e_count * (e_count - 1)
                density = round((r_count / max_possible_relations) * 100, 2)

            # 2. 活用実績 (Utilization Facts)
            cursor = await conn.execute(
                "SELECT SUM(access_count), COUNT(*) FROM knowledge_metadata"
            )
            row = await cursor.fetchone()
            total_access = row[0] or 0
            accessed_units = row[1] or 0

            reuse_multiplier = 0.0
            if accessed_units > 0:
                reuse_multiplier = round(total_access / accessed_units, 2)

            # 3. 検索精度と「知の熟成度」 (Precision & Knowledge Age)
            cursor = await conn.execute(
                """
                SELECT results_count, hit_content_ids, avg_similarity, timestamp
                FROM search_stats
                WHERE results_count > 0
                """
            )
            hit_rows = await cursor.fetchall()
            q_total = "SELECT COUNT(*) FROM search_stats"
            total_searches_cursor = await conn.execute(q_total)
            total_searches = (await total_searches_cursor.fetchone())[0] or 0

            precision_sum = 0.0
            total_hits = len(hit_rows)
            # 熟成度分類 (Knowledge Maturity Distribution)
            maturity = {
                "intra_session": 0,  # 1時間以内 (Working Memory)
                "short_term": 0,  # 1〜24時間 (Next Day Transfer)
                "long_term": 0,  # 24時間以上 (Strategic Asset)
            }

            if total_hits > 0:
                import json

                for _r_count, hit_ids_json, avg_sim, s_ts in hit_rows:
                    precision_sum += avg_sim or 0.0
                    try:
                        hit_ids = json.loads(hit_ids_json or "[]")
                        if not hit_ids:
                            continue

                        # 最初のヒットIDのみで代表的な「知の年齢」を計測
                        target_id = hit_ids[0]
                        q_age = (
                            "SELECT created_at FROM entities WHERE name = ? "
                            "UNION "
                            "SELECT last_synced as created_at FROM bank_files "
                            "WHERE filename = ?"
                        )
                        c = await conn.execute(q_age, (target_id, target_id))
                        created_row = await c.fetchone()
                        if created_row:
                            # タイムスタンプ比較
                            s_dt = datetime.fromisoformat(s_ts.replace("Z", "+00:00"))
                            c_dt = datetime.fromisoformat(
                                created_row[0].replace(" ", "T").replace("Z", "+00:00")
                            )
                            age_hours = (s_dt - c_dt).total_seconds() / 3600

                            if age_hours < 1:
                                maturity["intra_session"] += 1
                            elif age_hours < 24:
                                maturity["short_term"] += 1
                            else:
                                maturity["long_term"] += 1
                    except Exception as e:
                        logger.warning(f"Failed to calculate maturity for hit record: {e}")
                        continue

            hit_rate = 0.0
            if total_searches > 0:
                hit_rate = round((total_hits / total_searches) * 100, 1)

            avg_precision = 0.0
            if total_hits > 0:
                avg_precision = round(precision_sum / total_hits, 2)

        async with await async_get_thoughts_connection() as conn_t:
            # 4. 推論ログの観測 (Reasoning Observation)
            cursor = await conn_t.execute("SELECT COUNT(*) FROM thought_history")
            t_count = (await cursor.fetchone())[0]
            cursor = await conn_t.execute("SELECT COUNT(DISTINCT session_id) FROM thought_history")
            s_count = (await cursor.fetchone())[0] or 1
            avg_steps = round(t_count / s_count, 1)

        return {
            "timestamp": datetime.now().isoformat(),
            "facts": {
                "stored_entities": e_count,
                "stored_relations": r_count,
                "stored_bank_files": b_count,
                "knowledge_graph_density_percent": density,
                "total_read_operations": total_access,
                "total_search_queries": total_searches,
                "search_hit_rate_percent": hit_rate,
                "avg_search_precision": avg_precision,
                "knowledge_maturity": maturity,
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
    def generate_report_markdown(metrics_data: dict[str, Any]) -> str:
        """
        主観的な主張を排除し、観測された事実のみを報告する。
        """
        f = metrics_data["facts"]
        i = metrics_data["efficiency_indicators"]

        report = f"""# SharedMemory Fact Report: 知識の「熟成」と「活用」
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
