from __future__ import annotations

from typing import Any

from ckan import types
from ckan.plugins import toolkit as tk


@tk.chained_auth_function
def package_delete(next_func: Any, context: types.Context, data_dict: dict[str, Any] | None) -> types.AuthResult:
    """Only sysadmins to delete datasets."""
    return {"success": False, "msg": "Only sysadmins can delete datasets."}


def yukon_matomo_sync_usage_data(context: types.Context, data_dict: dict[str, Any]) -> types.AuthResult:
    """Allow only sysadmins to trigger Matomo sync through the API."""
    return {"success": False, "msg": "Only sysadmins can trigger Matomo usage sync."}


def yukon_package_set_featured(context: types.Context, data_dict: dict[str, Any]) -> types.AuthResult:
    """Allow only sysadmins to set featured flag."""
    return {"success": False, "msg": "Only sysadmins can change featured state."}
