from __future__ import annotations

import logging
from typing import Any

from ckan import authz, model, types
from ckan.lib import search
from ckan.lib.search import rebuild
from ckan.plugins import toolkit as tk

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
    groups_list = data_dict.get("groups_list", False)
    if groups_list:
        if not isinstance(groups_list, list):
            groups_list = [groups_list]

        data_dict.pop("groups_list")
        data_dict["groups"] = [{"id": group_id} for group_id in groups_list]


@tk.side_effect_free
@tk.chained_action
def package_show(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
) -> Any:
    user = context.get("user")
    result = up_func(context, data_dict)
    org_id = result["organization"]["id"]
    if not can_view_internal_data(user, org_id):
        result.pop("internal_contact_name", None)
        result.pop("internal_contact_email", None)
        result.pop("internal_notes", None)
    return result


@tk.side_effect_free
@tk.chained_action
def package_search(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
) -> Any:
    user = context.get("user")
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
    user = context.get("user")
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
def package_create(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
) -> Any:
    _set_groups_list(context, data_dict)

    return up_func(context, data_dict)


@tk.side_effect_free
@tk.chained_action
def package_update(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
) -> Any:
    _set_groups_list(context, data_dict)

    return up_func(context, data_dict)


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
            dataset = tk.get_action("package_show")(
                {"ignore_auth": True}, {"id": dataset_id}
            )
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
            {
                "is_featured": [
                    f"The following datasets do not exist: \
                        {', '.join(non_existent_datasets)}"
                ]
            }
        )

    if invalid_type_datasets:
        raise tk.ValidationError(
            {
                "is_featured": [
                    f"The following datasets are not of \
                type 'data': {', '.join(invalid_type_datasets)}"
                ]
            }
        )

    try:
        log.info("Starting package_set_featured for datasets: %s", dataset_ids)

        # Fetch all current featured datasets
        current_featured = tk.get_action("package_search")(
            {"ignore_auth": True}, {"fq": "is_featured:true", "rows": 1000}
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

        # Verify the changes were applied
        log.info("Verifying changes were applied...")
        for dataset_id in dataset_ids:
            try:
                package_dict = tk.get_action("package_show")(
                    {"ignore_auth": True}, {"id": dataset_id}
                )
                is_featured_value = package_dict.get("is_featured", "NOT_SET")
                log.info("Package %s featured=%s", dataset_id, is_featured_value)
            except Exception:  # noqa: BLE001, PERF203
                log.exception("Failed to verify package %s", dataset_id)

        # Manually update search index for affected packages
        # This ensures search queries work without updating metadata_modified
        try:
            package_ids_to_reindex = list(previous_featured_ids) + list(dataset_ids)
            for pkg_id in package_ids_to_reindex:
                try:
                    # Use rebuild function to force reindex
                    rebuild(package_id=pkg_id, only_missing=False, force=True)
                except Exception:  # noqa: BLE001, PERF203
                    # Try alternative method if rebuild fails
                    try:
                        package_dict = tk.get_action("package_show")(
                            {"ignore_auth": True}, {"id": pkg_id}
                        )
                        search_backend = search.get_backend()
                        search_backend.update_dict(package_dict)
                    except Exception as e:  # noqa: BLE001, PERF203
                        log.warning("Skipping package due to error: %s", e)
                        # Skip this package if both methods fail
        except Exception as index_error:  # noqa: BLE001
            # Log the error but don't fail the operation
            log.warning("Failed to update search index: %s", index_error)
    except Exception as e:  # noqa: BLE001
        # Rollback any changes
        model.repo.rollback()
        raise tk.ValidationError(
            {"is_featured": [f"Failed to set featured datasets: {str(e)}"]}
        ) from e
    else:
        return {"success": True, "message": "Featured datasets updated successfully."}


def _update_package_extra(package_obj: model.Package, key: str, value: Any) -> None:
    """Update a package extra field without changing metadata_modified.

    :param package_obj: The package object
    :param key: The extra field key
    :param value: The new value for the extra field
    """
    log.info("Updating package %s extra %s to %s", package_obj.id, key, value)

    # First, let's see what extras already exist
    existing_extras = (
        model.Session.query(model.PackageExtra)
        .filter_by(package_id=package_obj.id)
        .all()
    )
    log.info("Package %s has %s extras", package_obj.id, len(existing_extras))
    for extra in existing_extras:
        log.info("  - %s = %s", extra.key, extra.value)

    # Try to find the specific extra we want to update
    existing_extra = (
        model.Session.query(model.PackageExtra)
        .filter_by(package_id=package_obj.id, key=key)
        .first()
    )

    if existing_extra:
        log.info("Found existing extra %s = %s", key, existing_extra.value)
        if value in ["False", "false", ""]:
            # Remove the extra if setting to false
            log.info("Deleting extra %s", key)
            model.Session.delete(existing_extra)
        else:
            # Update existing extra
            old_value = existing_extra.value
            existing_extra.value = value
            log.info("Updated extra %s from %s to %s", key, old_value, value)
    else:
        log.info("No existing extra %s found", key)
        if value not in ["False", "false", ""]:
            # Create new extra only if value is truthy
            log.info("Creating new extra %s with value %s", key, value)
            new_extra = model.PackageExtra(
                package_id=package_obj.id, key=key, value=value
            )
            model.Session.add(new_extra)
            log.info("Added new extra: %s = %s", new_extra.key, new_extra.value)

    # Flush to ensure the change is in the session
    model.Session.flush()
    log.info("Session flushed")

    # Verify the extra was created/updated
    verify_extra = (
        model.Session.query(model.PackageExtra)
        .filter_by(package_id=package_obj.id, key=key)
        .first()
    )

    if verify_extra:
        log.info("Verification: extra %s = %s", key, verify_extra.value)
    else:
        log.warning("Verification: extra %s not found after update!", key)

    log.info("Package %s extra %s update completed", package_obj.id, key)
