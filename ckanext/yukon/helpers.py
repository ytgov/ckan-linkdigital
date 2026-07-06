from __future__ import annotations

import fnmatch
import logging
from typing import Any

import ckan.plugins.toolkit as tk
from ckan import model, types

from ckanext.scheming.helpers import scheming_get_dataset_schema  # pyright: ignore[reportUnknownVariableType]

from . import config

log = logging.getLogger(__name__)


def recently_updated_open_informations() -> list[dict[str, str]]:
    """Returns a list of 3 recently updated open informations."""
    result = tk.get_action("package_search")(
        {},
        {"fq": "type:information", "sort": "metadata_modified desc", "rows": 3, "fl": "title,name,dataset_type"},
    )
    # Drop all the fields except the ones we need: title, name and type
    return [
        {
            "title": item["title"],
            "name": item["name"],
            "type": item["dataset_type"],
        }
        for item in result["results"]
    ]


def recently_added_access_requests():
    """Returns a list of 3 recently added access requests."""
    result = tk.get_action("package_search")(
        {"ignore_auth": True},
        {"fq": "type:access-requests", "sort": "metadata_created desc", "rows": 3},
    )  # Bypass auth
    # Drop all the fields except the ones we need: title, name and type
    packages = []
    for item in result["results"]:
        package = {}
        package["title"] = item["title"]
        package["name"] = item["name"]
        package["type"] = item["type"]
        packages.append(package)

    return packages


def get_featured_datasets():
    """Returns a list of all featured datasets."""
    try:
        # First try the search index
        result = tk.get_action("package_search")(
            {"ignore_auth": True},
            {
                "fq": "is_featured:true AND type:data",
                "rows": 1000,
                "sort": "metadata_created desc",
            },
        )

        # If search returns results, use them
        if result["results"]:
            return result["results"]

        # Fallback: Query database directly for packages with is_featured extra
        featured_packages = []

        # Get all packages with is_featured extra set to True
        extras_query = (
            model.Session.query(model.PackageExtra)
            .filter(
                model.PackageExtra.key == "is_featured",
                model.PackageExtra.value == "True",
            )
            .all()
        )

        for extra in extras_query:
            try:
                # Get the full package data
                package_dict = tk.get_action("package_show")({"ignore_auth": True}, {"id": extra.package_id})
                # Only include if it`s a data type package
                if package_dict.get("type") == "data":
                    featured_packages.append(package_dict)
            except Exception:  # noqa: BLE001, PERF203
                # Skip packages that can"t be shown
                log.warning('Skip package: %s  that can"t be shown', extra.package_id)
                continue
    except Exception:  # noqa: BLE001
        # Log the error for debugging
        log.exception("Error getting featured datasets.")
        return []
    else:
        return featured_packages


def group_is_empty(data_dict: types.DataDict, group_name: str, dataset_type: str):
    """Returns True if the group is empty, False otherwise."""
    dataset_fields = scheming_get_dataset_schema(dataset_type)["dataset_fields"]
    group_fields = []
    for field in dataset_fields:
        try:
            if field["group_name"] == group_name:
                if data_dict.get(field["field_name"]):
                    group_fields.append(field["field_name"])
                if field["field_name"] == "tag_string" and data_dict.get("tags"):
                    group_fields.append("tags")
                if field["field_name"] == "groups_list" and data_dict.get("groups"):
                    group_fields.append("groups")
        except KeyError:  # noqa: PERF203
            pass
    return len(group_fields) == 0


def dataset_type_title(dataset_type: str, plural: bool = True):
    """Convert dataset type to a human-readable title.

    Supporting singular and plural.
    """
    mapping = {
        "pia-summaries": (
            "Privacy Impact Assessment summary",
            "Privacy Impact Assessment summaries",
        ),
        "information": ("Open information", "Open information"),
        "data": ("Open data", "Open data"),
        "access-requests": (
            "Completed access to information request",
            "Completed access to information requests",
        ),
    }

    title_pair = mapping.get(dataset_type, (dataset_type, dataset_type))
    return title_pair[1] if plural else title_pair[0]


def dataset_type_menu_title(dataset_type: str):
    """Convert dataset type to a human-readable title for menus, translated."""
    _ = tk._
    mapping = {
        "pia-summaries": _("a PIA summary"),
        "information": _("open information"),
        "data": _("open data"),
        "access-requests": _("a completed access request"),
    }
    return mapping.get(dataset_type, _(dataset_type))


def matomo_siteid():
    """Adds the Matomo site ID to the template context.

    This is used for tracking purposes.
    """
    # Get the Matomo site ID from the CKAN configuration.
    # Uses CKANEXT__YUKON__MATOMO__SITE_ID env var.
    return tk.config.get("ckanext.yukon.matomo.site_id", "1")
    # Return the Matomo site ID for direct use in templates


def matomo_url():
    """Returns the Matomo tracking URL from the configuration.

    Uses CKANEXT__YUKON__MATOMO__TRACKER_URL for browser tracking,
    separate from the API_URL which is used for stats queries.
    """
    # Get the Matomo tracker URL from configuration (CKANEXT__YUKON__MATOMO__TRACKER_URL)
    # Falls back to analytics.gov.yk.ca if not set
    tracker_url: str = tk.config.get("ckanext.yukon.matomo.tracker_url", "https://analytics.gov.yk.ca/")

    # Ensure the URL ends with a trailing slash for the tracking code
    if not tracker_url.endswith("/"):
        tracker_url += "/"

    return tracker_url


def get_year_facet_items(facet_name: str, search_facets: dict[str, Any]):
    """Get facet items for the year_published facet, sorted chronologically (newest first).

    This overrides the default facet sorting which is by count, and instead sorts
    by year in descending order (most recent years first).

    :param facet_name: The name of the facet field (should be 'year_published')
    :param search_facets: Dictionary containing all search facets
    :return: List of facet items sorted by year (newest first)
    """
    if not search_facets or facet_name not in search_facets:
        return []

    facet_data = search_facets.get(facet_name, {})
    items = facet_data.get("items", [])

    # Sort items by year in descending order (newest first)
    # Each item has 'name' (the year) and 'count' (number of datasets)
    return sorted(items, key=lambda x: x.get("name", ""), reverse=True)


def yukon_allow_local_login() -> bool:
    """Check if IP is whitelisted for local login."""
    ip = tk.request.headers.get(config.ip_header(), tk.request.remote_addr)

    if not ip:
        log.warning("Cannot determine IP using %s header", config.ip_header())
        return False
    return any(fnmatch.fnmatch(ip, value) for value in config.safe_ips())


def downloadall__count_uploaded_resources(pkg: dict[str, Any]):
    """Counts the number of uploaded resources in a package.

    Excludes linked resources. Uploaded resources have url_type == 'upload'.
    """
    count = 0
    for res in pkg.get("resources", []):
        # Don't count the downloadall zip itself
        if res.get("downloadall_metadata_modified"):
            continue
        # Only count uploaded resources, not linked ones
        if res.get("url_type") == "upload":
            count += 1
    return count
