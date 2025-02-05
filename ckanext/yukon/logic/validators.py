from __future__ import annotations

from typing import Any

import ckan.plugins.toolkit as tk
from ckan import types, authz
import ckan.lib.navl.dictization_functions as df

Invalid = df.Invalid


def yukon_required(value: Any):
    """Verify that value is not empty."""
    if not value or value is tk.missing:
        raise tk.Invalid("Required")

    return value


def yukon_complex_validator(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
):
    """Verify that value is not empty."""
    if not data[key]:
        errors[key].append("Required")
        raise tk.StopOnError


def yukon_user_name_validator(key: types.FlattenKey, data: types.FlattenDataDict,
                        errors: types.FlattenErrorDict, context: types.Context) -> Any:
    '''
        Copy of the original 'user_name_validator' CKAN Validator,
        but without a part that restrict name changing.
    '''
    model = context['model']
    new_user_name = data[key]

    if not isinstance(new_user_name, str):
        raise Invalid(_('User names must be strings'))

    user = model.User.get(new_user_name)
    user_obj_from_context = context.get('user_obj')
    if user is not None:
        # A user with new_user_name already exists in the database.
        if user_obj_from_context and user_obj_from_context.id == user.id:
            # If there's a user_obj in context with the same id as the user
            # found in the db, then we must be doing a user_update and not
            # updating the user name, so don't return an error.
            return
        else:
            # Otherwise return an error: there's already another user with that
            # name, so you can't create a new user with that name or update an
            # existing user's name to that name.
            errors[key].append(_('That login name is not available.'))
    elif user_obj_from_context:
        requester = context.get('auth_user_obj', None)
        if requester and authz.is_sysadmin(requester.name):
            return
