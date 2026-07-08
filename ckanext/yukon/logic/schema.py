from __future__ import annotations

import ckan.plugins.toolkit as tk
from ckan import types


@tk.validator_args
def package_set_featured(
    list_of_strings: types.Validator, default: types.ValidatorFactory, json_list_or_string: types.Validator
) -> types.Schema:
    return {
        "dataset_ids": [default("[]"), json_list_or_string, list_of_strings],
    }


@tk.validator_args
def matomo_sync_usage_data(
    list_of_strings: types.Validator,
    default: types.ValidatorFactory,
    json_list_or_string: types.Validator,
    boolean_validator: types.Validator,
    int_validator: types.Validator,
) -> types.Schema:
    return {
        "dry_run": [boolean_validator],
        "dataset_refs": [default("[]"), json_list_or_string, list_of_strings],
        "limit": [default(25), int_validator],
        "offset": [default(0), int_validator],
    }
