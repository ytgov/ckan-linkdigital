from __future__ import annotations

from typing import Any

from typing_extensions import override

import ckan.plugins as p
import ckan.plugins.toolkit as tk
from ckan.lib.plugins import DefaultTranslation

from . import helpers, implementations
from .logic import action, auth


@tk.blanket.auth_functions(
    {
        "package_delete": auth.package_delete_sysadmin_only,
        "yukon_matomo_sync_usage_data": auth.yukon_matomo_sync_usage_data_sysadmin_only,
    }
)
@tk.blanket.actions(
    {
        "package_show": action.package_show,
        "package_search": action.package_search,
        "current_package_list_with_resources": (action.current_package_list_with_resources),
        "package_create": action.package_create,
        "package_update": action.package_update,
        "package_set_featured": action.package_set_featured,
        "yukon_matomo_sync_usage_data": action.yukon_matomo_sync_usage_data,
    }
)
@tk.blanket.helpers(
    {
        "get_all_groups": helpers.get_all_groups,
        "recently_updated_open_informations": (helpers.recently_updated_open_informations),
        "recently_added_access_requests": (helpers.recently_added_access_requests),
        "group_is_empty": helpers.group_is_empty,
        "get_featured_datasets": helpers.get_featured_datasets,
        "get_current_year": helpers.get_current_year,
        "dataset_type_title": helpers.dataset_type_title,
        "dataset_type_menu_title": helpers.dataset_type_menu_title,
        "matomo_siteid": helpers.add_matomo_siteid_to_context,
        "matomo_url": helpers.matomo_url,
        "yukon_allow_local_login": helpers.yukon_allow_local_login,
        "get_year_facet_items": helpers.get_year_facet_items,
        "downloadall__count_uploaded_resources": helpers.downloadall__count_uploaded_resources,
    }
)
@tk.blanket.blueprints
@tk.blanket.cli
@tk.blanket.config_declarations
@tk.blanket.validators
class YukonPlugin(
    implementations.Theme,
    implementations.PackageController,
    implementations.CkanSaml,
    implementations.Ingest,
    DefaultTranslation,
    p.SingletonPlugin,
):
    """Main entrypoint of the yukon plugin."""

    p.implements(p.ITranslation)
    p.implements(p.IFacets)

    # ITranslation
    @override
    def i18n_locales(self):
        return ["en", "fr"]

    # IFacets
    def dataset_facets(self, facets_dict: dict[str, Any], package_type: str):
        """Add year_published to the dataset facets."""
        facets_dict["year_published"] = tk._("Year published")
        return facets_dict

    def organization_facets(self, facets_dict: dict[str, Any], organization_type: str, package_type: str | None):
        """Add year_published to the organization facets."""
        facets_dict["year_published"] = tk._("Year published")
        return facets_dict

    def group_facets(self, facets_dict: dict[str, Any], group_type: str, package_type: str | None):
        """Return facets for groups."""
        return facets_dict
