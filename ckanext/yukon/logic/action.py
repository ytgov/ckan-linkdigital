from __future__ import annotations

import logging
from typing import Any

from ckan import authz, model, types
from ckan.lib import search
from ckan.plugins import toolkit as tk

from ckanext.yukon import config, matomo_sync

from . import schema

log = logging.getLogger(__name__)


@tk.side_effect_free
@tk.chained_action
def package_show(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    """Hide internal fields if the user does not have permission to view them."""
    result = up_func(context, data_dict)
    org_id = result["organization"]["id"]
    if not _can_view_internal_data(context, org_id):
        result.pop("internal_contact_name", None)
        result.pop("internal_contact_email", None)
        result.pop("internal_notes", None)
    return result


@tk.side_effect_free
@tk.chained_action
def package_search(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    """Hide internal fields if the user does not have permission to view them."""
    result = up_func(context, data_dict)
    pkg_dicts = result["results"]

    for pkg_dict in pkg_dicts:
        if "organization" not in pkg_dict or not _can_view_internal_data(context, pkg_dict["organization"]["id"]):
            pkg_dict.pop("internal_contact_name", None)
            pkg_dict.pop("internal_contact_email", None)
            pkg_dict.pop("internal_notes", None)

    return result


@tk.side_effect_free
@tk.chained_action
def current_package_list_with_resources(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
) -> Any:
    """Hide internal fields if the user does not have permission to view them."""
    results = up_func(context, data_dict)

    for result in results:
        org_id = result["organization"]["id"]
        if not _can_view_internal_data(context, org_id):
            result.pop("internal_contact_name", None)
            result.pop("internal_contact_email", None)
            result.pop("internal_notes", None)

    return results


@tk.side_effect_free
@tk.chained_action
def package_create(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    """Set the groups field in the data_dict from the groups_list before creating the package."""
    _set_groups_list(context, data_dict)
    return up_func(context, data_dict)


@tk.side_effect_free
@tk.chained_action
def package_update(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    """Set the groups field in the data_dict from the groups_list before updating the package."""
    _set_groups_list(context, data_dict)

    return up_func(context, data_dict)


@tk.validate_action_data(schema.package_set_featured)
def package_set_featured(context: Any, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Sets three datasets as featured and removes previous featured datasets.

    Ensures that exactly three dataset IDs are provided.
    If the process fails, retains the previous featured datasets.

    :param context: The context dictionary provided by CKAN
    :type context: dict
    :param data_dict: The data dictionary containing the dataset IDs
    :type data_dict: dict

    :returns: A success message or raises an error
    :rtype: str
    """
    tk.check_access("yukon_package_set_featured", context, data_dict)

    # Extract dataset IDs from data_dict
    dataset_ids = data_dict.get("dataset_ids")
    limit = config.featured_datasets_limit()
    if not dataset_ids or len(dataset_ids) != limit:
        raise tk.ValidationError(
            {
                "is_featured": [f"Exactly {limit} dataset IDs or names must be provided."],
            }
        )

    non_existent_datasets: list[str] = []
    invalid_type_datasets: list[str] = []

    clean_ids: set[str] = set()

    for dataset_id in dataset_ids:
        try:
            dataset = tk.get_action("package_show")(tk.fresh_context(context), {"id": dataset_id})
            # Check if the dataset type is 'data'
            if dataset.get("type") != "data":
                invalid_type_datasets.append(dataset_id)
            clean_ids.add(dataset["id"])

        except tk.ObjectNotFound:  # noqa: PERF203
            non_existent_datasets.append(dataset_id)

    if non_existent_datasets:
        raise tk.ValidationError(
            {"is_featured": [f"The following datasets do not exist: {', '.join(non_existent_datasets)}"]}
        )

    if invalid_type_datasets:
        raise tk.ValidationError(
            {"is_featured": [f"The following datasets are not of type 'data': {', '.join(invalid_type_datasets)}"]}
        )

    log.debug("Starting package_set_featured for datasets: %s", dataset_ids)

    # Fetch all current featured datasets
    current_featured: set[str] = {
        p["id"]
        for p in tk.get_action("package_search")(
            {"ignore_auth": True}, {"fq": "is_featured:true", "fl": "id", "rows": 1000}
        )["results"]
    }

    log.debug("Found %d currently featured datasets", len(current_featured))

    remove_flag = current_featured - clean_ids
    add_flag = clean_ids - current_featured

    for id in remove_flag | add_flag:
        is_featured = id in add_flag
        log.debug("Set featured flag on %s to %s", id, is_featured)

        if pkg := model.Package.get(id):
            pkg.extras["is_featured"] = str(is_featured).lower()
    model.Session.commit()

    search.rebuild(package_ids=list(remove_flag | add_flag))
    search.commit()

    return {"success": True, "message": "Featured datasets updated successfully."}


@tk.validate_action_data(schema.matomo_sync_usage_data)
def yukon_matomo_sync_usage_data(context: types.Context, data_dict: dict[str, Any]):
    """Sync usage counters from Matomo into package extras.

    This action is intended for scheduled/API-triggered syncs and defaults to
    a conservative batch size to avoid overloading Matomo.
    """
    tk.check_access("yukon_matomo_sync_usage_data", context, data_dict)

    dry_run: bool = data_dict["dry_run"]
    dataset_refs: list[str] = data_dict["dataset_refs"]
    offset = data_dict["offset"]
    limit = len(dataset_refs) or data_dict["limit"]

    # Optional hard ceiling from config. 0 or unset means unlimited.
    max_limit = config.matomo_sync_limit()
    if max_limit > 0 and limit > max_limit:
        raise tk.ValidationError({"limit": [f"Must be less than or equal to {max_limit}"]})

    summary: dict[str, Any] = matomo_sync.sync_usage_data(
        dry_run=dry_run,
        limit=limit,
        offset=offset,
        dataset_refs=dataset_refs,
    )
    summary["limit"] = limit
    summary["offset"] = offset
    summary["dataset_refs"] = dataset_refs
    return summary


def _can_view_internal_data(context: types.Context, org_id: str) -> bool:
    """Check if the user can view internal data for the given organization."""
    if context.get("ignore_auth"):
        return True

    user_obj = model.User.get(context["user"])
    if not user_obj:
        return False

    if user_obj.sysadmin:
        return True

    role = authz.users_role_for_group_or_org(org_id, user_obj.id)
    return role in ["admin", "editor"]


def _set_groups_list(context: types.Context, data_dict: types.DataDict):
    """Set the groupsfield in the data_dict from the groups_list."""
    # If the form omitted the field entirely, leave existing groups unchanged.
    # If the field is present but empty, treat that as an invalid submission
    # and raise a ValidationError so the UI shows a required-field message.
    if "groups_list" not in data_dict:
        return

    gl: str | list[Any] | tuple[Any] = data_dict.get("groups_list", [])
    if isinstance(gl, str) and not gl.strip() or isinstance(gl, list | tuple) and not any(bool(x) for x in gl):
        raise tk.ValidationError({"groups_list": ["Missing value"]})

    groups_list = gl
    if isinstance(groups_list, str):
        groups_list = [groups_list]

    # Build groups list, filtering out any empty values
    groups = []
    for group_id in [g for g in groups_list if g]:
        try:
            group = tk.get_action("group_show")(context, {"id": group_id})
        except Exception:  # noqa: S112
            # Ignore invalid group ids rather than crashing the update
            continue
        groups.append({key: group.get(key) for key in ("id", "name", "title")})
    data_dict.pop("groups_list", None)
    data_dict["groups"] = groups
