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


@register(_name="information")
class InformationFactory(factories.Dataset):
    type = "information"
    owner_org = factory.LazyFunction(lambda: OrganizationFactory()["id"])
    internal_contact_email = factory.Faker("email")
    internal_contact_name = factory.Faker("name")
    license_id = "cc-by"


@register(_name="access_request")
class AccessRequestFactory(factories.Dataset):
    type = "access-requests"
    owner_org = factory.LazyFunction(lambda: OrganizationFactory()["id"])
    date_of_request = factory.Faker("date")
    file_id = factory.Faker("uuid4")
    response_type = factory.Faker("random_element", elements=["not_specified", "granted_in_full", "no_records_found"])
    license_id = "cc-by"


@register(_name="pia_summary")
class PiaSummaryFactory(factories.Dataset):
    type = "pia-summaries"
    # owner_org = factory.LazyFunction(lambda: OrganizationFactory()["id"])
    # internal_contact_email = factory.Faker("email")
    # internal_contact_name = factory.Faker("name")
    # license_id = "cc-by"


@register(_name="organization")
class OrganizationFactory(factories.Organization):
    pass
