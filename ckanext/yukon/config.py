"""Config getters of yukon plugin."""

from __future__ import annotations

import ckan.plugins.toolkit as tk

OPTION = "ckanext.yukon.option.name"
MULTI = "ckanext.yukon.multivalued.option"


def option() -> int:
    """Integer placerat tristique nisl."""
    return tk.config[OPTION]


def multivalued() -> list[str]:
    """Another option that will be parsed as a list of words."""
    return tk.config[MULTI]
