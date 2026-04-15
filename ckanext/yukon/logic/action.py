from __future__ import annotations

import logging
import traceback
from typing import Any

from ckan import authz, model, types
from ckan.lib import search
from ckan.plugins import toolkit as tk

from ckanext.yukon import matomo_sync

log = logging.getLogger(__name__)
FEATURED_DATASETS_COUNT = 3


def is_user_editor_of_org(org_id: str, user_id: str) -> bool:
    """Check if the user is an editor of the organization."""
    capacity = authz.users_role_for_group_or_org(org_id, user_id)
    return capacity == "editor"


def is_user_admin_of_org(org_id: str, user_id: str) -> bool:
    """Check if the user is an admin of the organization."""
    capacity = authz.users_role_for_group_or_org(org_id, user_id)
    return capacity == "admin"


def is_user_sysadmin(user_id: str) -> bool:
    """Check if the user is a sysadmin."""
    user = model.User.get(user_id)
    if user:
        return user.sysadmin
    return False


def can_view_internal_data(user: str, org_id: str) -> bool:
    """Check if the user can view internal data for the given organization."""
    if not user:
        return False

    user_obj = model.User.get(user)
    if not user_obj:
        return False

    user_id = user_obj.id

    if is_user_sysadmin(user_id):
        return True
    if is_user_admin_of_org(org_id, user_id):
        return True
    return bool(is_user_editor_of_org(org_id, user_id))


def _set_groups_list(context: types.Context, data_dict: types.DataDict):
    """Set the groupsfield in the data_dict from the groups_list."""
    # If the form omitted the field entirely, leave existing groups unchanged.
    # If the field is present but empty, treat that as an invalid submission
    # and raise a ValidationError so the UI shows a required-field message.
    if "groups_list" not in data_dict:
        return

    gl: str | list[Any] | tuple[Any] = data_dict.get("groups_list", [])
    empty = False
    if isinstance(gl, str) and not gl.strip() or isinstance(gl, list | tuple) and not any(bool(x) for x in gl):
        empty = True
    if empty:
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


@tk.side_effect_free
@tk.chained_action
def package_show(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    user = context["user"]
    result = up_func(context, data_dict)
    package = model.Package.get(result["id"])
    if package:
        for key in ["visits", "downloads", "visit_90_days", "download_90_days"]:
            value = package.extras.get(key)
            if value is not None:
                result[key] = value
    org_id = result["organization"]["id"]
    if not can_view_internal_data(user, org_id):
        result.pop("internal_contact_name", None)
        result.pop("internal_contact_email", None)
        result.pop("internal_notes", None)
    return result


@tk.side_effect_free
@tk.chained_action
def package_search(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    user = context["user"]
    result = up_func(context, data_dict)
    pkg_dicts = result["results"]

    for pkg_dict in pkg_dicts:
        org_id = pkg_dict["organization"]["id"]
        if not can_view_internal_data(user, org_id):
            pkg_dict.pop("internal_contact_name", None)
            pkg_dict.pop("internal_contact_email", None)
            pkg_dict.pop("internal_notes", None)

    return result


@tk.side_effect_free
@tk.chained_action
def current_package_list_with_resources(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
) -> Any:
    user = context["user"]
    results = up_func(context, data_dict)

    for result in results:
        org_id = result["organization"]["id"]
        if not can_view_internal_data(user, org_id):
            result.pop("internal_contact_name", None)
            result.pop("internal_contact_email", None)
            result.pop("internal_notes", None)

    return results


@tk.side_effect_free
@tk.chained_action
def package_create(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    _set_groups_list(context, data_dict)

    return up_func(context, data_dict)


@tk.side_effect_free
@tk.chained_action
def package_update(up_func: types.Action, context: types.Context, data_dict: types.DataDict) -> Any:
    _set_groups_list(context, data_dict)

    return up_func(context, data_dict)


def yukon_matomo_sync_usage_data(context: types.Context, data_dict: dict[str, Any]):
    """Sync usage counters from Matomo into package extras.

    This action is intended for scheduled/API-triggered syncs and defaults to
    a conservative batch size to avoid overloading Matomo.
    """

    tk.check_access("yukon_matomo_sync_usage_data", context, data_dict)

    dry_run = bool(data_dict.get("dry_run", False))
    dataset_refs = data_dict.get("dataset_refs") or []
    limit = data_dict.get("limit")
    offset = data_dict.get("offset")

    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise tk.ValidationError({"limit": ["Must be an integer"]})

    if offset is not None:
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            raise tk.ValidationError({"offset": ["Must be an integer"]})

    if isinstance(dataset_refs, str):
        dataset_refs = [dataset_refs]
    elif not isinstance(dataset_refs, list | tuple):
        raise tk.ValidationError({"dataset_refs": ["Must be a string or a list of strings"]})

    # Keep API-triggered runs conservative unless the caller scopes them.
    if not dataset_refs and limit is None:
        limit = 25

    # Optional hard ceiling from config. 0 or unset means unlimited.
    max_limit = tk.config.get("ckanext.yukon.matomo.api_sync_max_limit", 0)
    try:
        max_limit = int(max_limit)
    except (TypeError, ValueError):
        max_limit = 0

    if max_limit > 0 and limit is not None and limit > max_limit:
        raise tk.ValidationError({"limit": [f"Must be less than or equal to {max_limit}"]})
    if offset is not None and offset < 0:
        raise tk.ValidationError({"offset": ["Must be greater than or equal to 0"]})

    summary: dict[str, Any] = matomo_sync.sync_usage_data(
        dry_run=dry_run,
        limit=limit,
        offset=offset,
        dataset_refs=list(dataset_refs) if dataset_refs else None,
    )
    summary["limit"] = limit
    summary["offset"] = offset or 0
    summary["dataset_refs"] = list(dataset_refs)
    return summary


def package_set_featured(context: Any, data_dict: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR0915, C901, PLR0912б, PLR0915
    """Sets three datasets as featured and removes previous featured datasets.

    Ensures that exactly three dataset IDs are provided.
    If the process fails, retains the previous featured datasets.

    Only sysadmins are allowed to use this API.

    :param context: The context dictionary provided by CKAN
    :type context: dict
    :param data_dict: The data dictionary containing the dataset IDs
    :type data_dict: dict

    :returns: A success message or raises an error
    :rtype: str
    """
    # Check if the user is a sysadmin
    user = context.get("user")
    if not user or not is_user_sysadmin(user):
        raise tk.NotAuthorized("Only sysadmins can use this API.")  # noqa: TRY003

    # Extract dataset IDs from data_dict
    dataset_ids = data_dict.get("dataset_ids")
    if not dataset_ids or len(dataset_ids) != FEATURED_DATASETS_COUNT:
        raise tk.ValidationError(
            {
                "is_fetured": ["Exactly three dataset IDs or names must be provided."],
            }
        )

    # Check if all provided datasets exist and are of type 'data'
    non_existent_datasets = []
    invalid_type_datasets = []
    package_objects = {}  # Store package objects for later use
    for dataset_id in dataset_ids:
        try:
            dataset = tk.get_action("package_show")({"ignore_auth": True}, {"id": dataset_id})
            # Check if the dataset type is 'data'
            if dataset.get("type") != "data":
                invalid_type_datasets.append(dataset_id)
            else:
                # Get the actual package object from the database
                package_obj = model.Package.get(dataset["id"])
                if package_obj:
                    # Use the original dataset_id as key, not the UUID
                    package_objects[dataset_id] = package_obj
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

    try:
        log.info("Starting package_set_featured for datasets: %s", dataset_ids)

        # Fetch all current featured datasets
        current_featured = tk.get_action("package_search")(
            {"ignore_auth": True}, {"fq": "is_featured:True", "rows": 1000}
        )["results"]

        log.info("Found %d currently featured datasets", len(current_featured))

        # Backup current featured dataset IDs
        previous_featured_ids = [pkg["id"] for pkg in current_featured]
        previous_featured_objects = {}

        # Get package objects for current featured datasets
        for pkg_id in previous_featured_ids:
            package_obj = model.Package.get(pkg_id)
            if package_obj:
                previous_featured_objects[pkg_id] = package_obj

        # Remove the "is_featured" flag from all current featured datasets
        for pkg_id in previous_featured_ids:
            package_obj = previous_featured_objects.get(pkg_id)
            if package_obj:
                log.info("Removing featured flag from package %s", pkg_id)
                # Update the extras directly without changing metadata_modified
                _update_package_extra(package_obj, "is_featured", "False")

        # Set the "is_featured" flag for the new datasets
        for dataset_id in dataset_ids:
            package_obj = package_objects.get(dataset_id)
            if package_obj:
                log.info("Setting featured flag for package %s", dataset_id)
                log.info("Pkg ID: %s, Name: %s", package_obj.id, package_obj.name)
                # Update the extras directly without changing metadata_modified
                _update_package_extra(package_obj, "is_featured", "True")
            else:
                log.error("No package object found for %s", dataset_id)

        log.info("Committing database changes")
        # Commit the changes
        model.repo.commit()

        # Manually update search index for affected packages
        # This ensures search queries work without updating metadata_modified
        # We need to do this AFTER commit so package_show returns updated extras

        package_ids_to_reindex = set(previous_featured_ids) | {package_objects[did].id for did in dataset_ids}

        log.info(f"Reindexing {len(package_ids_to_reindex)} packages in search index")

        # Get the search index backend
        search_backend = search.index_for("package")

        for pkg_id in package_ids_to_reindex:
            try:
                # Fetch the updated package data after commit
                package_dict = tk.get_action("package_show")({"ignore_auth": True}, {"id": pkg_id})
                is_featured_value = package_dict.get("is_featured", "NOT_SET")
                log.info(f"Reindexing package {pkg_id}, is_featured={is_featured_value}")

                # Update the search index with the current package data
                search_backend.index_package(package_dict, defer_commit=False)
                log.info(f"Successfully reindexed package {pkg_id}")
            except Exception as e:
                log.error(f"Failed to reindex package {pkg_id}: {e}")

                log.error(traceback.format_exc())
                # Continue with other packages even if one fails
                continue

        # Commit all changes to Solr
        search_backend.commit()
        log.info("Search index committed")

        return {"success": True, "message": "Featured datasets updated successfully."}
    except Exception as e:  # noqa: BLE001
        # Rollback any changes
        model.repo.rollback()
        raise tk.ValidationError({"is_featured": [f"Failed to set featured datasets: {str(e)}"]}) from e
    else:
        return {"success": True, "message": "Featured datasets updated successfully."}


def _update_package_extra(package_obj: model.Package, key: str, value: Any):
    """Helper function to update a package extra field without changing
    metadata_modified.

    :param package_obj: The package object
    :param key: The extra field key
    :param value: The new value for the extra field
    """

    log = logging.getLogger(__name__)

    log.info(f"Updating package {package_obj.id} extra {key} to {value}")

    # Try to find the specific extra we want to update
    existing_extra = model.Session.query(model.PackageExtra).filter_by(package_id=package_obj.id, key=key).first()

    if existing_extra:
        log.info(f"Found existing extra {key} = {existing_extra.value}")
        # Always update the value, even if it's 'False'
        # This ensures the search index can properly filter on the field
        old_value = existing_extra.value
        existing_extra.value = value
        log.info("Updated extra %s from %s to %s", key, old_value, value)
    else:
        log.info(f"No existing extra {key} found, creating new one")
        # Always create the extra, even if value is 'False'
        new_extra = model.PackageExtra(package_id=package_obj.id, key=key, value=value)
        model.Session.add(new_extra)
        log.info("Added new extra: %s = %s", key, value)

    # Flush to ensure the change is in the session
    model.Session.flush()

    log.info("Session flushed")

    # Verify the extra was created/updated
    verify_extra = model.Session.query(model.PackageExtra).filter_by(package_id=package_obj.id, key=key).first()

    if verify_extra:
        log.info("Verification: extra %s = %s", key, verify_extra.value)
    else:
        log.warning("Verification: extra %s not found after update!", key)

    log.info("Package %s extra %s update completed", package_obj.id, key)
