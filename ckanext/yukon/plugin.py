"""Definition of the main plugin.

If you have multiple plugins, it's recommended to create `plugins` module and
put every plugin into a separate submodule. Or even create a separate extension
for every plugin, if they are not really related.

It's possible to put multiple plugins into single module, but it may affect a
bit order of plugin in CKAN v2.10 because of implementation details of plugins
core. If order of plugins does not change anything, it's safe to define plugins
in the same file.

Blankets decorating the plugin are used to provide default implementation of
corresponding interfaces. When blanket is applied, it reads content from the
certain module and register it using CKAN Interface.

Source module for blanket is defined by CKAN recommendations. `cli` blanket
reads content from `cli.py`, `actions` blanket reads content from
`logic/action.py`, etc.

If you have a different project structure, you have two alternatives. Blankets
accept either a collection of items for corresponding interface, or a function
that can produce such collection.

Example:
    ```python
    def get_actions():
        return {"yukon_something": something}

    helpers = {"yukon_hello": hello}

    @tk.blanket.actions(get_actions)
    @tk.blanket.helpers(helpers)
    class YukonPlugin(...):
        ...
    ```
"""

from __future__ import annotations

from typing import Any

from typing_extensions import override

import ckan.plugins as p
import ckan.plugins.toolkit as tk
from ckan.common import CKANConfig
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
        'matomo_url': helpers.matomo_url,
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
    # implementations are extracted to separate modules to keep main plugin
    # definition as lean as possible
    implementations.PackageController,
    implementations.CkanSaml,
    implementations.Ingest,
    DefaultTranslation,
    # don't forget to extend SingletonPlugin. Due to internal
    # implementation details, it must be extended directly by the plugin
    p.SingletonPlugin,
):
    """Main entrypoint of the yukon plugin.

    This plugin does nothing yet, but it will definitely grow into beautiful
    and useful plugin one day.
    """

    # it's still possible to implement interfaces directly inside the main
    # plugin. But do it only if implementation is really straightforward and
    # compact
    p.implements(p.ITranslation)
    p.implements(p.IConfigurer)
    p.implements(p.IFacets)

    # ITranslation
    @override
    def i18n_locales(self):
        return ["en", "fr"]

    # IConfigurer
    def update_config(self, config_: CKANConfig):
        """Modify CKAN configuration."""
        # register templates of the plugin
        tk.add_template_directory(config_, "templates")

        # every file from the public directory can be accessed directly from
        # the browser. Use this for public images, site logos, downloadable
        # documents.
        tk.add_public_directory(config_, "public")

        # register assets folder. You must add `webassets.yml` into this folder
        tk.add_resource("assets", "yukon")

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
