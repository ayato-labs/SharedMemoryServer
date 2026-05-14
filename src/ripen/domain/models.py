from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class Relation:
    subject: str
    object: str
    predicate: str
    agent_id: str = "default"
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class Observation:
    entity_name: str
    content: str
    agent_id: str = "default"
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    timestamp: Optional[datetime] = None


@dataclass(frozen=True)
class BankFile:
    filename: str
    content: str
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    last_synced: Optional[datetime] = None
