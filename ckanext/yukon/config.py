"""Config getters of yukon plugin."""

from __future__ import annotations

import ckan.plugins.toolkit as tk

IP_HEADER = "ckanext.yukon.login.ip_header"
SAFE_IPS = "ckanext.yukon.login.safe_ip"
ADDED_REQUEST_LIMIT = "ckanext.yukon.limits.added_request"
UPDATED_INFO_LIMIT = "ckanext.yukon.limits.updated_information"
FEATURED_LIMIT = "ckanext.yukon.limits.featured_datasets"
MATOMO_SITE_ID = "ckanext.yukon.matomo.site_id"
MATOMO_URL = "ckanext.yukon.matomo.tracker_url"
MATOMO_API_URL = "ckanext.yukon.matomo.api_url"
MATOMO_TOKEN = "ckanext.yukon.matomo.token_auth"  # noqa: S105
MATOMO_TIMEOUT = "ckanext.yukon.matomo.timeout_seconds"
MATOMO_SYNC_LIMIT = "ckanext.yukon.matomo.api_sync_max_limit"


def ip_header() -> str:
    return tk.config[IP_HEADER]


def safe_ips() -> list[str]:
    return tk.config[SAFE_IPS]


def featured_datasets_limit() -> int:
    return tk.config[FEATURED_LIMIT]


def recent_requests_limit() -> int:
    return tk.config[ADDED_REQUEST_LIMIT]


def updated_informations_limit() -> int:
    return tk.config[UPDATED_INFO_LIMIT]


def matomo_site_id() -> str:
    return tk.config[MATOMO_SITE_ID]


def matomo_tracker_url() -> str:
    url = tk.config[MATOMO_URL]
    if not url.endswith("/"):
        url += "/"

    return url


def matomo_api_url() -> str:
    return tk.config[MATOMO_API_URL].rstrip("/")


def matomo_token() -> str:
    return tk.config[MATOMO_TOKEN]


def matomo_timeout() -> int:
    return tk.config[MATOMO_TIMEOUT]


def matomo_sync_limit() -> int:
    return tk.config[MATOMO_SYNC_LIMIT]
