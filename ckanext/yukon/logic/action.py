from ckan import authz, model, types
from ckan.plugins import toolkit as tk

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
        groups = []
        if not isinstance(groups_list, list):
            groups_list = [groups_list]

        groups = [{"id": group_id} for group_id in groups_list]

        data_dict.pop("groups_list")
        data_dict["groups"] = groups


@tk.side_effect_free
@tk.chained_action
def package_show(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
):
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
):
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
):
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
):
    _set_groups_list(context, data_dict)

    return up_func(context, data_dict)


@tk.side_effect_free
@tk.chained_action
def package_update(
    up_func: types.Action, context: types.Context, data_dict: types.DataDict
):
    _set_groups_list(context, data_dict)

    return up_func(context, data_dict)


def package_set_featured(context: types.Context, data_dict: types.DataDict):
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
        raise tk.NotAuthorized("Only sysadmins can use this API.")

    # Extract dataset IDs from data_dict
    dataset_ids = data_dict.get("dataset_ids")
    if not dataset_ids or len(dataset_ids) != FEATURED_DATASETS_COUNT:
        raise tk.ValidationError("Exactly three dataset IDs or names must be provided.")

    _validate_datasets(dataset_ids)

    previous_featured_ids: list[str] = []

    try:
        # Fetch all current featured datasets
        current_featured = tk.get_action("package_search")(
            {"ignore_auth": True}, {"fq": "is_featured:true", "rows": 1000}
        )["results"]

        # Backup current featured dataset IDs
        previous_featured_ids = [pkg["id"] for pkg in current_featured]

        # Remove the "is_featured" flag from all current featured datasets
        for pkg_id in previous_featured_ids:
            # Fetch the existing dataset details
            existing_dataset = tk.get_action("package_show")(
                {"ignore_auth": True}, {"id": pkg_id}
            )
            # Update the dataset with "is_featured" set to False
            existing_dataset["is_featured"] = False
            tk.get_action("package_update")({"ignore_auth": True}, existing_dataset)

        # Set the "is_featured" flag for the new datasets
        for dataset_id in dataset_ids:
            # Fetch the existing dataset details
            existing_dataset = tk.get_action("package_show")(
                {"ignore_auth": True}, {"id": dataset_id}
            )
            # Ensure all required fields are present
            if "internal_contact_email" not in existing_dataset:
                existing_dataset["internal_contact_email"] = ""
            if "internal_contact_name" not in existing_dataset:
                existing_dataset["internal_contact_name"] = ""
            if "license_id" not in existing_dataset:
                existing_dataset["license_id"] = "notspecified"  # Default value

            # Update the dataset with "is_featured" set to True
            existing_dataset["is_featured"] = True
            tk.get_action("package_update")({"ignore_auth": True}, existing_dataset)

        return {"success": True, "message": "Featured datasets updated successfully."}

    except Exception as e:
        # If any error occurs, restore the previous featured datasets
        for pkg_id in previous_featured_ids:
            # Fetch the existing dataset details
            existing_dataset = tk.get_action("package_show")(
                {"ignore_auth": True}, {"id": pkg_id}
            )
            # Restore the "is_featured" flag
            existing_dataset["is_featured"] = True
            tk.get_action("package_update")({"ignore_auth": True}, existing_dataset)
        raise tk.ValidationError(f"Failed to set featured datasets: {str(e)}") from e


def _validate_datasets(dataset_ids: list[str]) -> None:
    """Check if all provided datasets exist and are of type 'data'."""
    non_existent_datasets = []
    invalid_type_datasets = []
    for dataset_id in dataset_ids:
        try:
            dataset = tk.get_action("package_show")(
                {"ignore_auth": True}, {"id": dataset_id}
            )
            # Check if the dataset type is 'data'
            if dataset.get("type") != "data":
                invalid_type_datasets.append(dataset_id)
        except tk.ObjectNotFound:
            non_existent_datasets.append(dataset_id)

    if non_existent_datasets:
        raise tk.ValidationError(
            f"The following datasets do not exist: {', '.join(non_existent_datasets)}"
        )

    if invalid_type_datasets:
        raise tk.ValidationError(
            f"The following datasets are not of type 'data': "
            f"{', '.join(invalid_type_datasets)}"
        )
