from __future__ import annotations

import datetime
from typing import Any

from typing_extensions import override

import ckan.plugins as p


class PackageController(p.IPackageController):
    """Customize dataset lifecycle."""

    @override
    def before_dataset_index(self, pkg_dict: dict[str, Any]):
        """Add year_published field to the search index."""
        pkg_dict["year_published"] = datetime.datetime.fromisoformat(pkg_dict["metadata_created"]).year

        return pkg_dict
