from __future__ import annotations

from ckan import model, types

from ckanext.yukon.model import PackageStats


def yukon_package_stats(prop: str):

    def validator(
        key: types.FlattenKey, data: types.FlattenDataDict, errors: types.FlattenErrorDict, context: types.Context
    ):
        id = data.get(key[:-1] + ("id",))
        if stats := model.Session.get(PackageStats, id):
            data[key] = getattr(stats, prop)

    return validator
