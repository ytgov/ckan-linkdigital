from __future__ import annotations

from typing import Any

import ckan.plugins.toolkit as tk
from ckan import types
from ckan.logic.schema import user_edit_form_schema

from ckanext.toolbelt.decorators import Collector

action, get_actions = Collector("yukon").split()


@action("user_update")
@tk.chained_action
def user_update(next_: Any, context: types.Context, data_dict: dict[str, Any]):
    """
        Remove validation for Name while updating User in Yukon.
        
        Only SSO User be able to enter the portal, so it is not critical.
    """
    context["schema"] = _patch_user_schema(
        context.get("schema", user_edit_form_schema()),
    )

    user = next_(context, data_dict)

    return user


def _patch_user_schema(schema: types.Schema) -> types.Schema:
    schema["name"] = [
        tk.get_validator("not_empty"),
        tk.get_validator("name_validator"),
        tk.get_validator("yukon_user_name_validator"),
    ]
    return schema
