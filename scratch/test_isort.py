from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IAuditRepository


class AuditRepository(BaseSQLiteRepository, IAuditRepository):
    pass
