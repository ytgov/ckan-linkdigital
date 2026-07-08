from __future__ import annotations

from typing import Any

import pytest

import ckan.plugins.toolkit as tk
from ckan import types
from ckan.tests.helpers import call_auth


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestPackageDelete:
    def test_author_cannot_delete(self, data_factory: types.TestFactory, user: dict[str, Any]):
        """User who is the author of a package cannot delete it."""
        data = data_factory(user=user)
        with pytest.raises(tk.NotAuthorized):
            call_auth("package_delete", {"user": user["name"]}, id=data["id"])

    def test_org_admin_cannot_delete(
        self,
        data_factory: types.TestFactory,
        user: dict[str, Any],
        organization_factory: types.TestFactory,
    ):
        """User who is an admin of the organization that owns a package cannot delete it."""
        org = organization_factory(users=[{"name": user["name"], "capacity": "admin"}])
        data = data_factory(owner_org=org["id"])
        with pytest.raises(tk.NotAuthorized):
            call_auth("package_delete", {"user": user["name"]}, id=data["id"])

    def test_sysadmin_can_delete(self, data: dict[str, Any], sysadmin: dict[str, Any]):
        """Sysadmin can delete a package."""
        assert call_auth("package_delete", {"user": sysadmin["name"]}, id=data["id"])


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestYukonMatomoSyncUsageData:
    def test_normal_user_cannot_sync(self, user: dict[str, Any]):
        """Normal user cannot sync usage data."""
        with pytest.raises(tk.NotAuthorized):
            call_auth("yukon_matomo_sync_usage_data", {"user": user["name"]})


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestYukonPackageSetFeatured:
    def test_normal_user_cannot_set_featured(self, user: dict[str, Any]):
        """Normal user cannot set featured flag."""
        with pytest.raises(tk.NotAuthorized):
            call_auth("yukon_package_set_featured", {"user": user["name"]})
