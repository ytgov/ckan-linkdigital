from __future__ import annotations

from typing import Any

import factory
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


@register(_name="data")
class DataFactory(factories.Dataset):
    type = "data"
    owner_org = factory.LazyFunction(lambda: OrganizationFactory()["id"])
    internal_contact_email = factory.Faker("email")
    internal_contact_name = factory.Faker("name")
    license_id = "cc-by"



@register(_name="organization")
class OrganizationFactory(factories.Organization):
    pass
