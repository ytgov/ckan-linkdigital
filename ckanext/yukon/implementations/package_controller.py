from __future__ import annotations

import datetime
from typing import Any

from typing_extensions import override

import ckan.plugins as p


class PackageController(p.IPackageController):
    """Customize dataset lifecycle."""

    @override
    def before_dataset_index(self, pkg_dict: dict[str, Any]):
        """Add year_published field to the search index and exclude downloadall-generated resources from the facet."""
        pkg_dict["year_published"] = datetime.datetime.fromisoformat(pkg_dict["metadata_created"]).year

        # Remove downloadall auto-generated ZIP resources from the indexed
        # res_format facet. By the time before_dataset_index is called, CKAN
        # has already flattened resources into parallel arrays (res_name,
        # res_format, etc.) and popped the 'resources' list. We identify
        # downloadall ZIPs by their always-fixed name "All resource data".
        res_names = pkg_dict.get("res_name", [])
        res_formats = pkg_dict.get("res_format", [])
        if res_names and res_formats:
            keep = [
                i
                for i, name in enumerate(res_names)
                if not (name == "All resource data" and i < len(res_formats) and res_formats[i].upper() == "ZIP")
            ]
            if len(keep) < len(res_names):
                for key in ("res_name", "res_description", "res_format", "res_url", "res_type"):
                    arr = pkg_dict.get(key, [])
                    if arr:
                        pkg_dict[key] = [arr[i] for i in keep if i < len(arr)]

        return pkg_dict
