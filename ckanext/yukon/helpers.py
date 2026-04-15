"""Template helpers of the yukon plugin.

All non-private functions defined here are registered inside `tk.h` collection.
"""

from __future__ import annotations

import datetime
import fnmatch
import logging
from typing import Any

from ckan import model, types
from ckan.plugins import toolkit as tk

from ckanext.scheming.helpers import scheming_get_dataset_schema  # pyright: ignore[reportUnknownVariableType]

from . import config

log = logging.getLogger(__name__)


def get_all_groups() -> list[str]:  # noqa: C901
    """Returns a list of all groups in CKAN."""
    try:
        # Log the raw template/request context for debugging
        c_userobj = getattr(tk.c, "userobj", None)
        c_user = getattr(tk.c, "user", None)
        log.debug("get_all_groups called: c.userobj=%r c.user=%r", c_userobj, c_user)

        # Return only groups that the current user is a member of.
        user = c_user or None
        if not c_userobj and not user:
            log.debug("No user in context; returning empty group list")
            return []

        # Determine the current user object. Templates often set `c.userobj`,
        # otherwise `c.user` may be a username.
        user_obj = c_userobj
        if not user_obj:
            user_identifier = c_user
            try:
                user_obj = model.User.get(user_identifier)
            except Exception:
                user_obj = None
            if not user_obj:
                log.debug("Could not resolve user object for identifier=%r", user_identifier)
                return []

        # Get all groups and check which ones the user is a member of
        try:
            all_groups = tk.get_action("group_list")({"ignore_auth": True}, {"all_fields": True, "sort": "name"})
            log.debug("Found %d total groups", len(all_groups))

            user_groups = []
            for group in all_groups:
                try:
                    # Check if user is a member of this group
                    members = tk.get_action("member_list")(
                        {"ignore_auth": True}, {"id": group["id"], "object_type": "user"}
                    )
                    # Check if our user is in the members list
                    for member in members:
                        member_id = member[0] if isinstance(member, list | tuple) else member.get("id")
                        if str(member_id) == str(user_obj.id) or str(member_id) == str(user_obj.name):
                            user_groups.append(group)
                            log.debug("User %s is member of group %s", user_obj.name, group["name"])
                            break
                except Exception:
                    log.exception("Failed to check membership for group %s", group.get("id"))
                    continue

            if user_groups:
                log.debug("Returning %d groups for user %s", len(user_groups), user_obj.name)
                return user_groups
            log.debug("No groups found for user %s via action API", user_obj.name)
        except Exception:
            log.exception("Action API approach failed; falling back to DB scan")

        # Fallback: query Member rows and match in Python to support older/newer CKAN
        try:
            members = model.Session.query(model.Member).filter(model.Member.table_name == "group").all()

            log.debug("Found %d group membership rows total", len(members))

            group_ids = []
            for m in members:
                match = False
                candidates = [
                    getattr(m, "user_id", None),
                    getattr(m, "entity_id", None),
                    getattr(m, "ref", None),
                    getattr(m, "entity", None),
                    getattr(m, "user", None),
                ]
                for cand in candidates:
                    if cand is None:
                        continue
                    try:
                        if hasattr(cand, "id"):
                            cand_val = cand.id
                        elif hasattr(cand, "name"):
                            cand_val = cand.name
                        else:
                            cand_val = cand
                    except Exception:
                        cand_val = cand

                    try:
                        if str(cand_val) == str(user_obj.id) or str(cand_val) == str(user_obj.name):
                            match = True
                            break
                    except Exception:  # noqa: S112
                        continue
                if match:
                    gid = getattr(m, "table_id", None)
                    if gid:
                        group_ids.append(gid)

            groups = []
            for gid in group_ids:
                try:
                    group = tk.get_action("group_show")({"ignore_auth": True}, {"id": gid})
                except Exception:  # noqa: S112
                    continue
                groups.append(group)

            log.debug("Returning %d groups from DB scan for user id=%s", len(groups), user_obj.id)
            return groups
        except Exception as e:
            log.exception("Fallback DB scan failed: %r", e)
            return []
    except Exception as e:
        log.exception("Unexpected error in get_all_groups: %r", e)
        return []


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


def add_matomo_siteid_to_context():
    """Adds the Matomo site ID to the template context.

    This is used for tracking purposes.
    """
    # Get the Matomo site ID from the CKAN configuration.
    # Falls back to ckanext.yukon.matomo.site_id so a single env var
    # (CKANEXT__YUKON__MATOMO__SITE_ID) is sufficient.
    return tk.config.get("ckan.matomo_siteid", tk.config.get("ckanext.yukon.matomo.site_id", "1"))
    # Return the Matomo site ID for direct use in templates


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
