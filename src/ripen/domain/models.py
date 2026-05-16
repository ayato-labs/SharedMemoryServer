from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class KnowledgeStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class MaturityLevel(Enum):
    TRANSIENT = "TRANSIENT"
    OBSERVED = "OBSERVED"
    STABLE = "STABLE"


# Business Rules / Constants
STALE_ACCESS_THRESHOLD = 5
DEFAULT_GC_AGE_DAYS = 180


@dataclass(frozen=True)
class Entity:
    name: str
    entity_type: str = "concept"
    description: str = ""
    importance: int = 1
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Relation:
    subject: str
    object: str
    predicate: str
    agent_id: str = "default"
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    created_at: datetime | None = None


@dataclass(frozen=True)
class Observation:
    entity_name: str
    content: str
    agent_id: str = "default"
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    timestamp: datetime | None = None


@dataclass(frozen=True)
class BankFile:
    filename: str
    content: str
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    last_synced: datetime | None = None
