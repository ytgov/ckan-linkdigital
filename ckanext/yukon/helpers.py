"""Template helpers of the yukon plugin.

All non-private functions defined here are registered inside `tk.h` collection.
"""

from __future__ import annotations

import datetime
import fnmatch
import logging

from ckan import model, types
from ckan.plugins import toolkit as tk

from ckanext.scheming.helpers import scheming_get_dataset_schema

from . import config

log = logging.getLogger(__name__)


def get_all_groups() -> list[str]:
    """Returns a list of all groups in CKAN."""
    try:
        groups = tk.get_action("group_list")(
            {"ignore_auth": True}, {"all_fields": True}
        )  # Bypass auth
    except tk.ObjectNotFound:
        return []
    else:
        return groups


def recently_updated_open_informations() -> list[dict[str, str]]:
    """Returns a list of 3 recently updated open informations."""
    try:
        result = tk.get_action("package_search")(
            {"ignore_auth": True},
            {"fq": "type:information", "sort": "metadata_modified desc", "rows": 3},
        )  # Bypass auth
        # Drop all the fields except the ones we need: title, name and type
        packages = []
        for item in result["results"]:
            package = {
                "title": item["title"],
                "name": item["name"],
                "type": item["type"],
            }
            packages.append(package)
    except tk.ObjectNotFound:
        return []
    else:
        return packages


def recently_added_access_requests():
    """Returns a list of 3 recently added access requests."""
    try:
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
    except tk.ObjectNotFound:
        return []
    else:
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
                package_dict = tk.get_action("package_show")(
                    {"ignore_auth": True}, {"id": extra.package_id}
                )
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


def get_current_year():
    """Returns the current year as an integer."""
    return datetime.datetime.now().year


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


def dataset_type_menu_title(dataset_type: str) -> str:
    """Convert dataset type to a human-readable title for menus, translated."""
    _ = tk._
    mapping = {
        "pia-summaries": _("a PIA summary"),
        "information": _("open information"),
        "data": _("open data"),
        "access-requests": _("a completed access request"),
    }
    return mapping.get(dataset_type, _(dataset_type))


def add_matomo_siteid_to_context():
    """Adds the Matomo site ID to the template context.

    This is used for tracking purposes.
    """
    # Get the Matomo site ID from the CKAN configuration
    # Return the Matomo site ID for direct use in templates
    return tk.config.get("ckan.matomo_siteid", "1")


def yukon_allow_local_login() -> bool:
    """Check if IP is whitelisted for local login."""
    ip = tk.request.headers.get(config.ip_header(), tk.request.remote_addr)

    if not ip:
        log.warning("Cannot determine IP using %s header", config.ip_header())
        return False
    return any(fnmatch.fnmatch(ip, value) for value in config.safe_ips())
