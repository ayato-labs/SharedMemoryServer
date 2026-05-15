from typing import Any

from loguru import logger

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IManagementRepository


def foo():
    logger.info("test")
    x: Any = 1
    print(x, BaseSQLiteRepository, IManagementRepository)
