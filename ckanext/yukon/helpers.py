from __future__ import annotations

import fnmatch
import logging
from typing import Any

import ckan.plugins.toolkit as tk
from ckan import types

from ckanext.scheming.helpers import scheming_get_dataset_schema  # pyright: ignore[reportUnknownVariableType]

from . import config

log = logging.getLogger(__name__)


def yukon_recently_updated_open_informations() -> list[dict[str, str]]:
    """Returns a list of 3 recently updated open informations."""
    result = tk.get_action("package_search")(
        {},
        {
            "fq": "type:information",
            "sort": "metadata_modified desc",
            "rows": config.updated_informations_limit(),
            "fl": "title,name,dataset_type",
        },
    )

    return [
        {
            "title": item["title"],
            "name": item["name"],
            "type": item["dataset_type"],
        }
        for item in result["results"]
    ]


def yukon_recently_added_access_requests():
    """Returns a list of 3 recently added access requests."""
    result = tk.get_action("package_search")(
        {},
        {
            "fq": "type:access-requests",
            "sort": "metadata_created desc",
            "rows": config.recent_requests_limit(),
            "fl": "title,name,dataset_type",
        },
    )

    return [
        {
            "title": item["title"],
            "name": item["name"],
            "type": item["dataset_type"],
        }
        for item in result["results"]
    ]


def yukon_get_featured_datasets():
    """Returns featured datasets."""
    return tk.get_action("package_search")(
        {},
        {
            "fq": "is_featured:true AND type:data",
            "sort": "metadata_created desc",
        },
    )["results"]


def yukon_group_is_empty(data_dict: types.DataDict, group_name: str, dataset_type: str):
    """Check if the metadata group(set of dataset fields) is empty."""
    dataset_fields: list[dict[str, Any]] = scheming_get_dataset_schema(dataset_type)["dataset_fields"]
    for field in dataset_fields:
        if field.get("group_name") != group_name:
            continue

        name = field.get("field_name")

        if name == "tag_string":
            name = "tags"
        elif name == "groups_list":
            name = "groups"

        if data_dict.get(name):
            return False

    return True


def yukon_dataset_type_title(dataset_type: str, plural: bool = True):
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
    return title_pair[int(plural)]


def yukon_dataset_type_menu_title(dataset_type: str):
    """Convert dataset type to a human-readable title for menus, translated."""
    mapping = {
        "pia-summaries": tk._("a PIA summary"),
        "information": tk._("open information"),
        "data": tk._("open data"),
        "access-requests": tk._("a completed access request"),
    }
    return mapping.get(dataset_type, tk._(dataset_type))


def yukon_matomo_siteid():
    """Get configured value of the Matomo site ID."""
    return config.matomo_site_id()


def yukon_matomo_url():
    """Get configured value of the Matomo tracking URL."""
    return config.matomo_tracker_url()


def yukon_allow_local_login() -> bool:
    """Check if IP is whitelisted for local login."""
    if ip := tk.request.headers.get(config.ip_header(), tk.request.remote_addr):
        return any(fnmatch.fnmatch(ip, value) for value in config.safe_ips())

    log.warning("Cannot determine IP using %s header", config.ip_header())
    return False


def yukon_count_uploaded_resources(pkg: dict[str, Any]):
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
