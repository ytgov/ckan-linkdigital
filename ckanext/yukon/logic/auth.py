from __future__ import annotations

from ckan import types
from ckan.plugins import toolkit as tk


def package_delete_sysadmin_only(context: types.Context, data_dict: types.DataDict):
    """Auth function to allow only sysadmins to delete datasets."""
    # Check if user has sysadmin role
    if not tk.check_access("sysadmin", context):
        raise tk.NotAuthorized("Only sysadmins can delete datasets.")
    # Allow deletion
    return context


def yukon_matomo_sync_usage_data_sysadmin_only(context, data_dict):
    """Allow only sysadmins to trigger Matomo sync through the API."""
    if not tk.check_access('sysadmin', context):
        raise tk.NotAuthorized(
            "Only sysadmins can trigger Matomo usage sync."
        )
    return {'success': True}
