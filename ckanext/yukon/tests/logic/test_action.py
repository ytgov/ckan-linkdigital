from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from faker import Faker

import ckan.plugins.toolkit as tk
from ckan import types
from ckan.tests.helpers import call_action

from ckanext.yukon import config, matomo_sync


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestPackageShow:
    def test_internal_data_visibility(self, data: dict[str, Any], user_factory: types.TestFactory):
        """Internal data is only visible to editors and admins."""
        user = user_factory()
        editor = user_factory()
        call_action("member_create", object=editor["id"], capacity="editor", object_type="user", id=data["owner_org"])

        props = [
            "internal_contact_name",
            "internal_contact_email",
            # "internal_notes", # this field is optional and not added by factory
        ]

        result = call_action("package_show", {"user": user["name"], "ignore_auth": False}, id=data["id"])
        for prop in props:
            assert prop not in result

        result = call_action("package_show", {"user": editor["name"], "ignore_auth": False}, id=data["id"])
        for prop in props:
            assert prop in result


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestPackageSearch:
    def test_internal_data_visibility(self, data: dict[str, Any], user_factory: types.TestFactory):
        """Internal data is only visible to editors and admins."""
        user = user_factory()
        editor = user_factory()
        call_action("member_create", object=editor["id"], capacity="editor", object_type="user", id=data["owner_org"])

        props = [
            "internal_contact_name",
            "internal_contact_email",
            # "internal_notes", # this field is optional and not added by factory
        ]

        result = call_action("package_search", {"user": user["name"], "ignore_auth": False}, fq=f"id:{data['id']}")[
            "results"
        ][0]
        for prop in props:
            assert prop not in result

        result = call_action("package_search", {"user": editor["name"], "ignore_auth": False}, fq=f"id:{data['id']}")[
            "results"
        ][0]
        for prop in props:
            assert prop in result


@pytest.mark.usefixtures("with_plugins", "clean_db", "clean_index")
class TestCurrentPackageListWithResources:
    def test_internal_data_visibility(self, data: dict[str, Any], user_factory: types.TestFactory):
        """Internal data is only visible to editors and admins."""
        user = user_factory()
        editor = user_factory()
        call_action("member_create", object=editor["id"], capacity="editor", object_type="user", id=data["owner_org"])

        props = [
            "internal_contact_name",
            "internal_contact_email",
            # "internal_notes", # this field is optional and not added by factory
        ]

        result = call_action("current_package_list_with_resources", {"user": user["name"], "ignore_auth": False})[0]
        for prop in props:
            assert prop not in result

        result = call_action("current_package_list_with_resources", {"user": editor["name"], "ignore_auth": False})[0]
        for prop in props:
            assert prop in result


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestPackageCreate:
    def test_groups(self, data_factory: types.TestFactory, group: dict[str, Any]):
        """Groups can be added when package is created."""
        data = data_factory(groups_list=group["id"])
        assert len(data["groups"]) == 1
        assert data["groups"][0]["name"] == group["name"]


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestPackageUpdate:
    def test_groups(self, data: dict[str, Any], group: dict[str, Any], sysadmin: dict[str, Any]):
        """Groups can be added when package is updated."""
        data = call_action("package_patch", {"user": sysadmin["name"]}, id=data["id"], groups_list=group["id"])
        assert len(data["groups"]) == 1
        assert data["groups"][0]["name"] == group["name"]


@pytest.mark.usefixtures("with_plugins", "clean_db", "clean_index")
class TestSetFeatured:
    @pytest.mark.ckan_config(config.FEATURED_LIMIT, 2)
    def test_limit(self, data_factory: types.TestFactory):
        """Number of featured datasets is limited to FEATURED_LIMIT."""
        ids = [p["id"] for p in data_factory.create_batch(3)]
        with pytest.raises(tk.ValidationError):
            call_action("package_set_featured", dataset_ids=ids)

        with pytest.raises(tk.ValidationError):
            call_action("package_set_featured", dataset_ids=ids[:1])

        assert call_action("package_set_featured", dataset_ids=ids[:2])

    def test_flag_value(self, data_factory: types.TestFactory):
        """Featured flag is set to true for datasets that are marked as featured."""
        ids = [p["id"] for p in data_factory.create_batch(config.featured_datasets_limit() + 1)]

        results = call_action("package_search", rows=0, fq="is_featured:true")
        assert not results["count"]

        call_action("package_set_featured", dataset_ids=ids[:-1])

        results = call_action("package_search", rows=0, fq="is_featured:true")
        assert results["count"] == len(ids) - 1

    @pytest.mark.ckan_config(config.FEATURED_LIMIT, 1)
    def test_validation(self, information: dict[str, Any]):
        """Validation errors are raised when invalid dataset IDs are provided."""
        with pytest.raises(tk.ValidationError, match="not exist"):
            call_action("package_set_featured", dataset_ids=["not a real id"])

        with pytest.raises(tk.ValidationError, match="not of type"):
            call_action("package_set_featured", dataset_ids=[information["id"]])

    @pytest.mark.ckan_config(config.FEATURED_LIMIT, 1)
    def test_not_erasing_custom_fields(self, data_factory: types.TestFactory, faker: Faker):
        """Custom fields are not erased when setting featured datasets."""
        country = faker.country()
        data = data_factory(spatial_coverage_locations=country)
        call_action("package_set_featured", dataset_ids=[data["id"]])

        result = call_action("package_show", id=data["id"])
        assert result["spatial_coverage_locations"] == country


@pytest.mark.usefixtures("with_plugins", "clean_db", "clean_index")
class TestYukonMatomoSyncUsageData:
    def test_matomo_call(self, monkeypatch: pytest.MonkeyPatch):
        """Test that the action calls the sync_usage_data function with default parameters."""
        stub = mock.Mock(return_value={})
        monkeypatch.setattr(matomo_sync, "sync_usage_data", stub)
        call_action("yukon_matomo_sync_usage_data")
        stub.assert_called_once_with(dry_run=False, limit=25, offset=0, dataset_refs=[])

        call_action("yukon_matomo_sync_usage_data", dry_run=True, limit=4, offset=3)
        stub.assert_called_with(dry_run=True, limit=4, offset=3, dataset_refs=[])

        call_action("yukon_matomo_sync_usage_data", dataset_refs=["hello", "world"])
        stub.assert_called_with(dry_run=False, limit=2, offset=0, dataset_refs=["hello", "world"])
