from __future__ import annotations

from typing import Any

import pytest

import ckan.plugins.toolkit as tk
from ckan import types

from ckanext.yukon import config


@pytest.mark.usefixtures("with_plugins", "clean_db", "clean_index")
class TestRecentlyUpdatedOpenInformations:
    def test_only_information_included(self, information: dict[str, Any], data: dict[str, Any]):
        """Only information packages should be included in the recently updated open informations."""
        result = tk.h.yukon_recently_updated_open_informations()
        assert len(result) == 1
        assert result[0]["name"] == information["name"]

    def test_limit_and_order(self, information_factory: types.TestFactory):
        """Helper returns 3 latest items."""
        names = [item["name"] for item in information_factory.create_batch(5)]
        result = tk.h.yukon_recently_updated_open_informations()

        assert len(result) == config.updated_informations_limit()
        recent_names = [r["name"] for r in result]
        assert recent_names == names[-1:-4:-1]
        assert {r["type"] for r in result} == {"information"}


@pytest.mark.usefixtures("with_plugins", "clean_db", "clean_index")
class TestRecentlyAddedAccessRequests:
    def test_only_requests_included(self, access_request: dict[str, Any], data: dict[str, Any]):
        """Only request packages should be included in the recently added requests."""
        result = tk.h.yukon_recently_added_access_requests()
        assert len(result) == 1
        assert result[0]["name"] == access_request["name"]

    def test_limit_and_order(self, access_request_factory: types.TestFactory):
        """Helper returns 3 latest items."""
        names = [item["name"] for item in access_request_factory.create_batch(5)]
        result = tk.h.yukon_recently_added_access_requests()

        assert len(result) == config.recent_requests_limit()
        recent_names = [r["name"] for r in result]
        assert recent_names == names[-1:-4:-1]
        assert {r["type"] for r in result} == {"access-requests"}


@pytest.mark.usefixtures("with_plugins", "clean_db", "clean_index")
class TestGetFeaturedDatasets:
    def test_only_featured_included(self, data_factory: types.TestFactory):
        """Only datasets with featured flag should be included."""
        good = data_factory(is_featured=True)
        data_factory(is_featured=False)

        result = tk.h.yukon_get_featured_datasets()
        assert len(result) == 1
        assert result[0]["name"] == good["name"]

    def test_limit_and_order(self, data_factory: types.TestFactory):
        """Helper returns all featured datasets.

        This is the original behavior. May have sense to limit the number of
        dataset to configured maximum. API already uses it to restrict number
        of featured datasets, so there should be no more items that we set in config.
        """
        data_factory.create_batch(5, is_featured=True)
        result = tk.h.yukon_get_featured_datasets()

        assert len(result) == 5


@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestGroupIsEmpty:
    def test_data(self, data_factory: types.TestFactory):
        """Test function using the `data` package type."""
        data = data_factory(spatial_coverage_locations="")
        assert tk.h.yukon_group_is_empty(data, "data_coverage", data["type"])

        data = data_factory(spatial_coverage_locations="not empty")
        assert not tk.h.yukon_group_is_empty(data, "data_coverage", data["type"])


@pytest.mark.usefixtures("with_plugins")
class TestDatasetTypeTitle:
    def test_plural(self):
        """Test plural titles for dataset types."""
        assert tk.h.yukon_dataset_type_title("pia-summaries") == "Privacy Impact Assessment summaries"
        assert tk.h.yukon_dataset_type_title("pia-summaries", False) == "Privacy Impact Assessment summary"

    def test_missing(self):
        """The name of the type returned unchanged by default."""
        assert tk.h.yukon_dataset_type_title("not-real") == "not-real"
        assert tk.h.yukon_dataset_type_title("not-real", False) == "not-real"


@pytest.mark.usefixtures("with_plugins")
class TestDatasetMenuTitle:
    def test_plural(self):
        """Test title mapping for menu."""
        assert tk.h.yukon_dataset_type_menu_title("pia-summaries") == "a PIA summary"

    def test_missing(self):
        """The name of the type returned unchanged by default."""
        assert tk.h.yukon_dataset_type_title("not-real") == "not-real"


@pytest.mark.usefixtures("with_plugins")
class TestMatomoSiteId:
    def test_default(self):
        """The default Matomo site ID is returned when not set in the config."""
        assert tk.h.yukon_matomo_siteid() == "1"

    @pytest.mark.ckan_config(config.MATOMO_SITE_ID, "42")
    def test_custom(self):
        """The Matomo site ID is returned from the config when set."""
        assert tk.h.yukon_matomo_siteid() == "42"


@pytest.mark.usefixtures("with_plugins")
class TestMatomoSiteUrl:
    def test_default(self):
        """The default Matomo tracker URL is returned when not set in the config."""
        assert tk.h.yukon_matomo_url() == "https://analytics.gov.yk.ca/"

    @pytest.mark.ckan_config(config.MATOMO_URL, "https://google.com")
    def test_custom(self):
        """The Matomo tracker URL is returned from the config when set, and a trailing slash is added if missing."""
        assert tk.h.yukon_matomo_url() == "https://google.com/"


@pytest.mark.usefixtures("with_plugins")
class TestAllowLocalLogin:
    def test_default(self, test_request_context: types.FixtureTestRequestContext):
        """project.ini allows login from any IP."""
        with test_request_context(environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            assert tk.h.yukon_allow_local_login()
        with test_request_context(environ_base={"REMOTE_ADDR": "9.32.183.0"}):
            assert tk.h.yukon_allow_local_login()

    @pytest.mark.ckan_config(config.SAFE_IPS, ["*.*.*.42"])
    def test_safe(self, test_request_context: types.FixtureTestRequestContext):
        """Local login is allowed for IPs matching the safe IPs config."""
        with test_request_context(environ_base={"REMOTE_ADDR": "1.1.1.42"}):
            assert tk.h.yukon_allow_local_login()

        with test_request_context(environ_base={"REMOTE_ADDR": "1.1.1.43"}):
            assert not tk.h.yukon_allow_local_login()
