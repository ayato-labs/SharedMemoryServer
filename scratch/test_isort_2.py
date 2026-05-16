from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IAuditRepository


def foo(x: Any):
    pass

class AuditRepository(BaseSQLiteRepository, IAuditRepository):
    pass
