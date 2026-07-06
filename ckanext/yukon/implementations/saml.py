from __future__ import annotations

import logging
import re
from typing import Any

from typing_extensions import override

from ckanext.saml.interfaces import ICKANSAML

log = logging.getLogger(__name__)


class CkanSaml(ICKANSAML):
    @override
    def after_mapping(self, mapped_data: dict[str, Any], auth: Any):
        fullname_list = [
            mapped_data["givenname"][0] if mapped_data.get("givenname") else "",
            mapped_data["surname"][0] if mapped_data.get("givenname") else "",
        ]

        mapped_data["fullname"] = [" ".join(fullname_list).strip()]

        if mapped_data.get("name"):
            mapped_data["name"] = [re.sub(r"[^\w]", "_", mapped_data["name"][0]).lower()]
        return mapped_data
