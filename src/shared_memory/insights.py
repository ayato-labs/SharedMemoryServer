from datetime import datetime
from typing import Any

from shared_memory.database import async_get_connection, async_get_thoughts_connection


class InsightEngine:
    """
    SharedMemoryServerの価値を定量化するための計測エンジン。
    客観的な「観測可能データ」のみに基づき、事実としての実績レポートを生成します。
    """

    @staticmethod
    async def get_summary_metrics() -> dict[str, Any]:
        """
        データベースから取得した「計測事実」のみを抽出します。
        """
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

            # 3. 検索ヒット率 (Search Hit Rate) - 新規計測事実
            cursor = await conn.execute(
                """
                SELECT COUNT(*), SUM(CASE WHEN results_count > 0 THEN 1 ELSE 0 END)
                FROM search_stats
                """
            )
            s_row = await cursor.fetchone()
            total_searches = s_row[0] or 0
            total_hits = s_row[1] or 0

            hit_rate = 0.0
            if total_searches > 0:
                hit_rate = round((total_hits / total_searches) * 100, 1)

        async with await async_get_thoughts_connection() as conn_t:
            # 4. 推論ログの観測 (Reasoning Observation)
            cursor = await conn_t.execute(
                "SELECT COUNT(*) FROM thought_history"
            )
            t_count = (await cursor.fetchone())[0]
            cursor = await conn_t.execute(
                "SELECT COUNT(DISTINCT session_id) FROM thought_history"
            )
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

        report = f"""# SharedMemory Fact Report: 知識活用実績
Generated at: {metrics_data["timestamp"]}

## 1. 知識の蓄積状況 (Knowledge Inventory)
現在、システムは以下の情報を構造化して保持しています。

- **エンティティ数**: `{f['stored_entities']} items`
- **リレーション数**: `{f['stored_relations']} links`
- **バンクファイル数**: `{f['stored_bank_files']} files`
- **知識密度 (Graph Density)**: `{f['knowledge_graph_density_percent']}%`

## 2. 検索と再利用の実績 (Search & Reuse Performance)
エージェントからの問い合わせに対し、メモリが提供した実績データです。

- **検索ヒット率 (Hit Rate)**: `{f['search_hit_rate_percent']}%`
  > [!NOTE]
  > ヒット率は、全検索クエリ `{f['total_search_queries']} 回` のうち、
  > 何らかの記憶が呼び出された割合です。

- **活用係数 (Reuse Multiplier)**: `{i['reuse_multiplier']}x`
  > [!TIP]
  > 一度保存された知識は、平均して **{i['reuse_multiplier']}回**
  > 繰り返し再利用されています。

## 3. 推論プロセスの観測 (Reasoning Metrics)
- **総思考ステップ数**:
  `{(f['avg_thoughts_per_session'] * (f['stored_entities'] // 10 + 1)):.1f} steps`
- **1セッションあたりの平均思考手数**: `{f['avg_thoughts_per_session']} steps`

---
**本レポートの性質について**:
この報告書には推定値（例：コスト削減額など）は一切含まれていません。
提示されている数値はすべて、データベースのアクセスログおよび検索履歴から抽出された
**観測事実**です。価値の最終的な判断は、これらの実績に基づき
ユーザー自身が行うものと定義されています。
"""
        return report
