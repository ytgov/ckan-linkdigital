from __future__ import annotations

from typing import Any

import pytest

import ckan.plugins.toolkit as tk
from ckan import types
from ckan.tests.helpers import call_action


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestPackageShow:
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
