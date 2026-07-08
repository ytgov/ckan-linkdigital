from __future__ import annotations

from typing import Any

import ckan.plugins as p
import ckan.plugins.toolkit as tk
from ckan.lib.plugins import DefaultTranslation

from . import implementations


@tk.blanket.actions
@tk.blanket.auth_functions
@tk.blanket.blueprints
@tk.blanket.cli
@tk.blanket.config_declarations
@tk.blanket.helpers
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
