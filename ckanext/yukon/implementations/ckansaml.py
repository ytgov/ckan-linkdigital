from __future__ import annotations

import logging
from typing import Any


import ckan.plugins as p

from ckanext.saml.interfaces import ICKANSAML

log = logging.getLogger(__name__)


class CkanSaml(p.SingletonPlugin):
    p.implements(ICKANSAML, inherit=True)

    def after_mapping(self, mapped_data: dict[str, Any], auth: Any):
        fullname_list = [
            text for text in [
                mapped_data["givenname"][0] if \
                    mapped_data.get("givenname") else "",
                mapped_data["surname"][0] if \
                    mapped_data.get("givenname") else ""
            ]
        ]

        mapped_data["fullname"] = " ".join(fullname_list).strip()
        return mapped_data
