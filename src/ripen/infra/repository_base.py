from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class IBankRepository(ABC):
    @abstractmethod
    async def get_active_filenames(self) -> list[str]:
        pass

    @abstractmethod
    async def get_active_files_content(self) -> list[tuple[str, str]]:
        pass

    @abstractmethod
    async def get_all_files_content(self) -> list[tuple[str, str]]:
        pass

    @abstractmethod
    async def get_file_content(self, filename: str) -> str | None:
        pass

    @abstractmethod
    async def upsert_bank_file(self, filename: str, content: str, agent_id: str) -> None:
        pass

    @abstractmethod
    async def get_bank_files_by_names(self, names: list[str]) -> list[tuple[str, str]]:
        pass

    @abstractmethod
    async def update_status(self, filenames: str | list[str], status: str) -> int:
        pass

    @abstractmethod
    async def get_inactive_bank_files(self) -> list[dict[str, Any]]:
        pass


class IAuditRepository(ABC):
    @abstractmethod
    async def log_action(
        self,
        table_name: str,
        content_id: str,
        action: str,
        old_data: str | None,
        new_data: str,
        agent_id: str,
        meta_data: str | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def get_history(self, limit: int, table_name: str | None) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_audit_log_by_id(self, audit_id: int) -> dict[str, Any] | None:
        pass


class IEntityRepository(ABC):
    @abstractmethod
    async def get_all_entity_names(self) -> list[str]:
        pass

    @abstractmethod
    async def get_entity_details(self, name: str) -> dict | None:
        pass

    @abstractmethod
    async def upsert_entity(
        self,
        name: str,
        entity_type: str,
        description: str,
        importance: int,
        agent_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def increment_importance(self, name: str) -> None:
        pass

    @abstractmethod
    async def get_entities_by_names(self, names: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def update_status(self, names: str | list[str], status: str) -> int:
        pass

    @abstractmethod
    async def get_inactive_entities(self) -> list[dict[str, Any]]:
        pass


class IRelationRepository(ABC):
    @abstractmethod
    async def upsert_relation(
        self, subject: str, object_name: str, predicate: str, agent_id: str
    ) -> None:
        pass

    @abstractmethod
    async def upsert_relations_bulk(self, relations: Sequence[tuple[str, str, str, str]]) -> None:
        pass

    @abstractmethod
    async def get_relations_by_subjects_or_objects(self, names: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_relations_by_entity(self, entity_name: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def update_status(self, subject: str, object: str, predicate: str, status: str) -> None:
        pass

    @abstractmethod
    async def update_status_by_entities(self, names: list[str], status: str) -> int:
        pass

    @abstractmethod
    async def get_inactive_relations(self) -> list[dict[str, Any]]:
        pass


class IObservationRepository(ABC):
    @abstractmethod
    async def get_recent_observations(self, entity_name: str, limit: int = 5) -> list[str]:
        pass

    @abstractmethod
    async def insert_observation(self, entity_name: str, content: str, agent_id: str) -> None:
        pass

    @abstractmethod
    async def get_observations_by_entity_names(self, names: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_active_observations_by_entity(self, entity_name: str) -> list[tuple[str, str]]:
        pass

    @abstractmethod
    async def update_status(self, obs_id: int, status: str) -> None:
        pass

    @abstractmethod
    async def update_status_by_entities(self, names: list[str], status: str) -> int:
        pass

    @abstractmethod
    async def get_inactive_observations(self) -> list[dict[str, Any]]:
        pass


class ISearchRepository(ABC):
    @abstractmethod
    async def perform_fts_search(
        self,
        fts_table: str,
        id_col: str,
        content_col: str,
        title_col: str,
        fts_query: str,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def perform_like_search(
        self, table: str, id_col: str, content_col: str, query: str
    ) -> list[dict[str, Any]]:
        pass


class IConflictRepository(ABC):
    @abstractmethod
    async def insert_conflict(
        self,
        entity_name: str,
        existing_content: str,
        new_content: str,
        reason: str,
        agent_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def get_unresolved_conflicts(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_conflict_by_id(self, conflict_id: int) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def mark_resolved(self, conflict_id: int) -> None:
        pass


class IEmbeddingRepository(ABC):
    @abstractmethod
    async def get_cached_embedding(self, content_hash: str, model_name: str) -> list[float] | None:
        """Get a cached embedding by content hash and model name."""
        pass

    @abstractmethod
    async def insert_cache_entry(
        self, content_hash: str, vector: list[float], model_name: str
    ) -> None:
        """Insert a new entry into the embedding cache."""
        pass

    @abstractmethod
    async def get_all_embeddings(self) -> list[tuple[str, bytes]]:
        """Retrieve all stored embeddings for hybrid search."""
        pass


class ITroubleshootingRepository(ABC):
    @abstractmethod
    async def insert_troubleshooting(
        self, title: str, solution: str, affected_functions: str, env_metadata: str
    ) -> None:
        pass

    @abstractmethod
    async def get_troubleshooting_by_ids(self, ids: list[int]) -> list[dict[str, Any]]:
        pass


class ITagRepository(ABC):
    @abstractmethod
    async def replace_tags(self, content_id: str, content_type: str, tags: list[str]) -> None:
        pass

    @abstractmethod
    async def get_content_ids_by_tags(self, tags: list[str]) -> list[str]:
        pass

    @abstractmethod
    async def search_tags(self, query_words: list[str]) -> list[dict[str, Any]]:
        pass


class IGraphRepository(ABC):
    @abstractmethod
    async def get_full_graph(self, limit: int = 100) -> tuple[list[dict], list[dict], list[dict]]:
        pass

    @abstractmethod
    async def search_graph(
        self, query: str
    ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        pass


class IMetadataRepository(ABC):
    @abstractmethod
    async def get_all_metadata(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def update_access(self, content_id: str) -> None:
        pass

    @abstractmethod
    async def get_access_stats_summary(self) -> dict[str, Any]:
        pass

    @abstractmethod
    async def get_successful_search_stats(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_total_search_count(self) -> int:
        pass

    @abstractmethod
    async def log_search_stat(
        self, query: str, results_count: int, hit_ids: list[str], avg_sim: float = 0.0
    ) -> None:
        pass


class IThoughtRepository(ABC):
    @abstractmethod
    async def init_tables(self) -> None:
        pass

    @abstractmethod
    async def insert_thought(
        self,
        session_id: str,
        thought_number: int,
        total_thoughts: int,
        thought: str,
        next_thought_needed: bool,
        is_revision: bool,
        revises_thought: int | None,
        branch_from_thought: int | None,
        branch_id: str | None,
        agent_id: str,
        meta_data: str | None,
    ) -> None:
        pass

    @abstractmethod
    async def mark_session_distilled(self, session_id: str) -> None:
        """Mark a session as distilled."""
        pass

    @abstractmethod
    async def get_undistilled_sessions(self) -> list[str]:
        """Get all session IDs that have not been distilled."""
        pass

    @abstractmethod
    async def get_session_history(self, session_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_total_thought_count(self) -> int:
        pass

    @abstractmethod
    async def get_total_session_count(self) -> int:
        pass

    @abstractmethod
    async def search_thoughts(
        self, fts_query: str, exclude_session_id: str
    ) -> list[dict[str, Any]]:
        pass


class IManagementRepository(ABC):
    @abstractmethod
    async def get_table_info(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def vacuum_into(self, target_path: str) -> None:
        pass

    @abstractmethod
    async def delete_stale_knowledge(self, age_days: int) -> int:
        pass

    @abstractmethod
    async def get_count(self, table_name: str) -> int:
        pass

    @abstractmethod
    async def get_creation_timestamp(self, content_id: str) -> str | None:
        pass

    @abstractmethod
    async def get_database_stats(self) -> dict[str, Any]:
        pass

    @abstractmethod
    async def get_embedding_model_distribution(self) -> dict[str, int]:
        pass

    @abstractmethod
    async def get_isolated_entities(self) -> list[str]:
        pass

    @abstractmethod
    async def get_entity_type_distribution(self) -> dict[str, int]:
        pass

    @abstractmethod
    async def get_agent_contribution_stats(self) -> dict[str, int]:
        pass

    @abstractmethod
    async def get_snapshot_path(self, snapshot_id: int) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def insert_snapshot(self, name: str, description: str, file_path: str) -> None:
        pass

    @abstractmethod
    async def list_snapshots(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def optimize_database(self) -> None:
        """Perform database optimization (PRAGMA optimize)."""
        pass

    @abstractmethod
    async def get_low_activity_ids(self, before_date: str, max_access_count: int) -> list[str]:
        """Identify IDs of knowledge items that have low activity based on access count and date."""
        pass
