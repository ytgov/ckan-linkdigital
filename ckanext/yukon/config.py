"""Config getters of yukon plugin."""

from __future__ import annotations

import ckan.plugins.toolkit as tk

IP_HEADER = "ckanext.yukon.login.ip_header"
SAFE_IPS = "ckanext.yukon.login.safe_ip"


def ip_header() -> str:
    return tk.config[IP_HEADER]


def safe_ips() -> list[str]:
    return tk.config[SAFE_IPS]
