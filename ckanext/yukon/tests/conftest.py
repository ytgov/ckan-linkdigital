from __future__ import annotations

from typing import Any

import pytest
from pytest_factoryboy import register

from ckan.tests import factories


@pytest.fixture
def clean_db(reset_db: Any, migrate_db_for: Any):
    """Apply plugin migrations whenever CKAN DB is cleaned."""
    reset_db()
    migrate_db_for("activity")
    migrate_db_for("saml")
    migrate_db_for("harvest")
    migrate_db_for("yukon")


@register(_name="datset")
class DatasetFactory(factories.Dataset):
    pass
