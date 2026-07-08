from __future__ import annotations

import calendar
import contextlib
import datetime
import http.client
import json
import logging
from typing import Any
from urllib.parse import urlencode, urlparse

import sqlalchemy as sa

from ckan import model
from ckan.exceptions import CkanConfigurationException
from ckan.plugins import toolkit as tk

from . import config

log = logging.getLogger(__name__)

SUPPORTED_TYPES = ["data", "information", "access-requests", "pia-summaries"]
USAGE_EXTRA_KEYS = ["visits", "downloads", "visit_90_days", "download_90_days"]


class MatomoClient:
    base_url: str
    site_id: str
    token_auth: str
    timeout: int

    def __init__(self):
        self.base_url = config.matomo_api_url()
        self.site_id = config.matomo_site_id()
        self.token_auth = config.matomo_token()
        self.timeout = config.matomo_timeout()

    def _http_conn(self):
        parsed = urlparse(self.base_url)
        host = parsed.hostname
        if not host:
            msg = f"Cannot parse host: {self.base_url}"
            raise CkanConfigurationException(msg)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.scheme == "https":
            return http.client.HTTPSConnection(host, port, timeout=self.timeout)
        return http.client.HTTPConnection(host, port, timeout=self.timeout)

    def _bulk_call(self, requests_payload: list[dict[str, Any]]) -> list[list[dict[str, Any]] | dict[str, Any]]:
        params = {
            "module": "API",
            "method": "API.getBulkRequest",
            "format": "JSON",
        }
        body = {"token_auth": self.token_auth}
        for idx, request_payload in enumerate(requests_payload):
            query = urlencode(request_payload, doseq=True)
            body[f"urls[{idx}]"] = f"?{query}"
        parsed = urlparse(self.base_url)
        path = parsed.path.rstrip("/") + "/index.php?" + urlencode(params)
        encoded_body = urlencode(body, doseq=True).encode("utf-8")
        conn = self._http_conn()
        try:
            conn.request(
                "POST",
                path,
                body=encoded_body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
        finally:
            conn.close()
        data = json.loads(raw)
        if isinstance(data, dict):
            raise tk.ValidationError(f"Matomo API error: {data}")

        return data

    def _visits_payload(self, page_url: str, periods: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """Build sub-request entries for page visit counts (per dataset URL)."""
        return [
            {
                "module": "API",
                "method": "Actions.getPageUrl",
                "idSite": self.site_id,
                "period": period,
                "date": date_value,
                "pageUrl": page_url,
                "format": "JSON",
            }
            for period, date_value in periods
        ]

    def _downloads_site_payload(self, periods: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """Build sub-request entries for site-wide download counts (archive-backed)."""
        return [
            {
                "module": "API",
                "method": "Actions.getDownloads",
                "idSite": self.site_id,
                "period": period,
                "date": date_value,
                "format": "JSON",
                "filter_limit": "-1",
                "flat": "1",
            }
            for period, date_value in periods
        ]

    @staticmethod
    def _sum_visits(responses: list[list[dict[str, Any]] | dict[str, Any]]):
        total = 0
        for response in responses:
            if isinstance(response, list) and response:
                response = response[0]
            if not isinstance(response, dict):
                log.warning("Unexpected visit record: %s", response)
                continue

            total += response.get("nb_visits", 0)
        return total

    @staticmethod
    def _build_download_map(responses: list[list[dict[str, Any]] | dict[str, Any]]) -> dict[str, Any]:
        """Aggregate nb_hits by normalised download URL across all period responses."""
        url_hits: dict[str, Any] = {}
        for response in responses:
            rows = response if isinstance(response, list) else []
            for row in rows:
                raw_url: str = row.get("Actions_DownloadUrl") or row.get("label") or ""
                if not raw_url or row.get("is_summary"):
                    continue

                # Normalise: strip scheme, lowercase, no trailing slash
                parsed = urlparse(raw_url if "://" in raw_url else "http://" + raw_url)
                key = (parsed.netloc.lower() + parsed.path).rstrip("/")
                hits = 0
                with contextlib.suppress(TypeError, ValueError):
                    hits = int(float(row.get("nb_hits", 0)))
                url_hits[key] = url_hits.get(key, 0) + hits
        return url_hits

    def prefetch_downloads(self, periods: list[tuple[str, str]]) -> dict[str, Any]:
        """Fetch site-wide download counts for all periods in one bulk request.
        Returns a dict mapping normalised URL path to total hit count.
        """
        payload = self._downloads_site_payload(periods)
        if not payload:
            return {}
        responses = self._bulk_call(payload)
        return self._build_download_map(responses)

    def fetch_page_visits(self, page_url: str, periods_3y: list[tuple[str, str]], periods_90d: list[tuple[str, str]]):
        """Fetch page visit counts for both time windows in one request."""
        v3y = self._visits_payload(page_url, periods_3y)
        v90 = self._visits_payload(page_url, periods_90d)
        split = len(v3y)
        combined = v3y + v90
        if not combined:
            return 0, 0
        responses = self._bulk_call(combined)
        visits_3y = self._sum_visits(responses[:split])
        visits_90d = self._sum_visits(responses[split:])
        return visits_3y, visits_90d

    def fetch_page_visits_multilang(
        self,
        page_urls: list[str],
        periods_3y: list[tuple[str, str]],
        periods_90d: list[tuple[str, str]],
    ):
        """Fetch page visit counts for multiple language URLs combined.

        Args:
            page_urls: List of URLs (e.g., English and French versions)
            periods_3y: Period chunks for 3-year window
            periods_90d: Period chunks for 90-day window

        Returns:
            Tuple of (visits_3y, visits_90d) summed across all URLs
        """
        if not page_urls:
            return 0, 0

        all_payloads_3y: list[dict[str, Any]] = []
        all_payloads_90d: list[dict[str, Any]] = []

        for url in page_urls:
            all_payloads_3y.extend(self._visits_payload(url, periods_3y))
            all_payloads_90d.extend(self._visits_payload(url, periods_90d))

        split = len(all_payloads_3y)
        combined = all_payloads_3y + all_payloads_90d

        if not combined:
            return 0, 0

        # Group the API bulk request calls into 24-chunk batches.
        responses = []

        for i in range(0, len(combined), 24):
            responses.extend(self._bulk_call(combined[i : i + 24]))

        visits_3y = self._sum_visits(responses[:split])
        visits_90d = self._sum_visits(responses[split:])
        return visits_3y, visits_90d


def _sum_downloads_from_map(
    download_map: dict[str, Any],
    candidate_urls: list[str],
    package_id: str,
    package_type: str,
):
    """Sum download hits for a dataset's resource URLs from a pre-fetched site-wide map.

    Uploaded files: match any map key that contains the package resource path prefix.
    External URLs: match by normalised URL.
    """
    package_prefix = f"/{package_type}/{package_id}/resource/"
    total = 0
    for url in candidate_urls:
        if not url:
            continue
        if package_prefix in url:
            # Uploaded file — sum all download URLs that belong to this package
            for key, hits in download_map.items():
                if package_prefix in key:
                    total += hits
            # Only count prefix once even if multiple resources share the package path
            break
        parsed = urlparse(url if "://" in url else "http://" + url)
        key = (parsed.netloc.lower() + parsed.path).rstrip("/")
        total += download_map.get(key, 0)
    return total


def _shift_years(value: datetime.date, years: int):
    year = value.year + years
    day = min(value.day, calendar.monthrange(year, value.month)[1])
    return datetime.date(year, value.month, day)


def _download_period_chunks(start_date: datetime.date, end_date: datetime.date) -> list[tuple[str, str]]:
    """Break a date range into yearly batches for download prefetch queries.

    Yearly batches avoid the silent per-sub-request filter_limit cap that occurs with 3
    years' worth of monthly chunks, while staying small enough to avoid server OOM that
    happens with a single 3-year range.
    """
    chunks: list[tuple[str, str]] = []
    current = start_date

    while current <= end_date:
        year_end = datetime.date(current.year, 12, 31)
        range_end = min(year_end, end_date)
        chunks.append(("range", f"{current.isoformat()},{range_end.isoformat()}"))

        current = datetime.date(current.year + 1, 1, 1)
    return chunks


def _month_chunks(start_date: datetime.date, end_date: datetime.date) -> list[tuple[str, str]]:
    """Break a date range using period=month for full months, period=range for partial
    edges."""
    chunks: list[tuple[str, str]] = []
    current = start_date

    while current <= end_date:
        if current.day == 1:
            last_day = calendar.monthrange(current.year, current.month)[1]
            month_end = datetime.date(current.year, current.month, last_day)

            if month_end <= end_date:
                chunks.append(("month", f"{current.year}-{current.month:02d}"))
                current = month_end + datetime.timedelta(days=1)
                continue

        last_day = calendar.monthrange(current.year, current.month)[1]
        month_end = datetime.date(current.year, current.month, last_day)
        range_end = min(month_end, end_date)
        chunks.append(("range", f"{current.isoformat()},{range_end.isoformat()}"))
        current = range_end + datetime.timedelta(days=1)

    return chunks


def _dataset_urls_multilang(package: model.Package) -> list[str]:
    """Get all language-variant URLs for a dataset (English + French).

    Returns a list of URLs to query for visit statistics, combining:
    - English URL: /{type}/{name}
    - French URL: /fr/{type}/{name}
    """
    site_url = tk.config.get("ckan.site_url", "").rstrip("/")
    dataset_type = (package.type or "dataset").strip("/")

    urls: list[str] = []

    # English URL
    if site_url:
        urls.append(f"{site_url}/{dataset_type}/{package.name}")
    else:
        urls.append(f"/{dataset_type}/{package.name}")

    # French URL
    if site_url:
        url_fr = f"{site_url}/fr/{dataset_type}/{package.name}"
        urls.append(url_fr)
    else:
        urls.append(f"/fr/{dataset_type}/{package.name}")

    return urls


def _dataset_download_urls(package: model.Package) -> list[str]:
    site_url = tk.config.get("ckan.site_url", "").rstrip("/")
    urls: list[str] = []
    for resource in package.resources:
        if resource.state != "active":
            continue
        if not resource.url:
            continue
        extras: dict[str, Any] = getattr(resource, "extras", None) or {}
        if "downloadall_datapackage_hash" in extras:
            continue

        resource_url = resource.url
        parsed = urlparse(resource_url)
        if parsed.scheme and parsed.netloc:
            urls.append(resource_url)
            continue

        if getattr(resource, "url_type", "") == "upload" and site_url:
            urls.append(
                "{}/{}/{}/resource/{}/download/{}".format(
                    site_url,
                    package.type,
                    package.id,
                    resource.id,
                    resource_url.lstrip("/"),
                )
            )
            continue

        urls.append(resource_url)
    return urls


def _upsert_extra(package_id: str, key: str, value: Any):
    return
    existing = model.Session.query(model.PackageExtra).filter_by(package_id=package_id, key=key).first()
    value = str(value)
    if existing:
        if existing.value != value:
            existing.value = value
            return True
        return False

    model.Session.add(model.PackageExtra(package_id=package_id, key=key, value=value))
    return True


def _active_packages_query(dataset_refs: list[str] | None = None):
    query = model.Session.query(model.Package).filter(
        model.Package.state == "active",
        model.Package.type.in_(SUPPORTED_TYPES),
    )
    if dataset_refs:
        query = query.filter(
            sa.or_(
                model.Package.name.in_(dataset_refs),
                model.Package.id.in_(dataset_refs),
            )
        )
    return query.order_by(model.Package.metadata_created.desc())


def _active_packages(dataset_refs: list[str] | None = None, limit: int | None = None, offset: int | None = None):
    query = _active_packages_query(dataset_refs=dataset_refs)
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)
    return query.all()


def sync_usage_data(
    dry_run: bool = False,
    limit: int | None = None,
    offset: int | None = None,
    dataset_refs: list[str] | None = None,
):
    if limit is not None and limit < 1:
        raise tk.ValidationError("--limit must be greater than 0")
    if offset is not None and offset < 0:
        raise tk.ValidationError("--offset must be greater than or equal to 0")

    client = MatomoClient()

    today = datetime.date.today()
    end_date = today - datetime.timedelta(days=1)
    last_90_start = end_date - datetime.timedelta(days=89)
    three_year_start = _shift_years(end_date, -3) + datetime.timedelta(days=1)

    processed = 0
    updated = 0
    skipped = 0
    failed = 0

    base_query = _active_packages_query(dataset_refs=dataset_refs)
    total = base_query.count()
    packages = _active_packages(
        dataset_refs=dataset_refs,
        limit=limit,
        offset=offset,
    )
    log.info("Matomo sync starting for %s package(s)", len(packages))

    download_periods_3y = _download_period_chunks(three_year_start, end_date)
    download_periods_90d = _download_period_chunks(last_90_start, end_date)
    visit_periods_3y = _month_chunks(three_year_start, end_date)
    visit_periods_90d = _month_chunks(last_90_start, end_date)
    log.info(
        "Matomo sync prefetching downloads: 3y=%s periods, 90d=%s periods",
        len(download_periods_3y),
        len(download_periods_90d),
    )
    download_map_3y = client.prefetch_downloads(download_periods_3y)
    download_map_90d = client.prefetch_downloads(download_periods_90d)
    log.info("Matomo sync download maps: 3y=%s urls, 90d=%s urls", len(download_map_3y), len(download_map_90d))

    for package in packages:
        processed += 1
        try:
            with model.Session.begin_nested():
                page_urls = _dataset_urls_multilang(package)
                download_urls = _dataset_download_urls(package)

                visits, visit_90_days = client.fetch_page_visits_multilang(
                    page_urls,
                    visit_periods_3y,
                    visit_periods_90d,
                )
                downloads = _sum_downloads_from_map(download_map_3y, download_urls, package.id, package.type)
                download_90_days = _sum_downloads_from_map(download_map_90d, download_urls, package.id, package.type)

                payload = {
                    "visits": visits,
                    "downloads": downloads,
                    "visit_90_days": visit_90_days,
                    "download_90_days": download_90_days,
                }

                package_changed = False
                for key in USAGE_EXTRA_KEYS:
                    if _upsert_extra(package.id, key, payload[key]):
                        package_changed = True

            if package_changed:
                updated += 1
            else:
                skipped += 1

            log.info(
                "Matomo sync package=%s changed=%s payload=%s",
                package.name,
                package_changed,
                payload,
            )
        except Exception as exc:
            failed += 1
            # Ensure any in-flight statement state is cleared before next pkg.
            model.Session.rollback()
            log.exception("Matomo sync failed for package=%s: %s", package.name, exc)

    if dry_run:
        model.Session.rollback()
    else:
        model.repo.commit()

    offset = offset or 0
    next_offset = offset + processed
    has_more = next_offset < total

    return {
        "processed": processed,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "dry_run": dry_run,
        "offset": offset,
        "total": total,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
    }
