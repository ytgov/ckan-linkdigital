from __future__ import annotations

import csv
import dataclasses
import logging
import os
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from io import StringIO
from typing import Any, Iterable

import requests
from sqlalchemy import and_

import ckan.plugins.toolkit as tk
from ckan import model, types
from ckan.lib import munge
from ckan.lib.uploader import get_resource_uploader

from ckanext.ingest import shared
from ckanext.ingest.record import PackageRecord, ResourceRecord
from ckanext.ingest.strategy.csv import CsvSimpleStrategy

from .redirect_map import RedirectMap

log = logging.getLogger(__name__)

RETRY_DELAY = 60
RESOURCE_NS = uuid.uuid3(uuid.NAMESPACE_DNS, "yukon_resource")
DKAN_PACKAGE_API = "https://open.yukon.ca/api/3/action/package_show?id={}"

DEFAULT_MAPPING = {
    "notes": "not_specified",
    "internal_contact_name": "not_specified",
    "internal_contact_email": "not_specified",
    "response_type": "not_specified",
}

RESOURCE_UNIQUE_FIELD = {
    "information": ["name", "created", "url", "dkan_parent_dataset_node_id"],
    "data": ["name", "created", "dkan_parent_dataset_node_id"],
    "access-requests": ["name", "created"],
}


class YukonCsvStrategy(CsvSimpleStrategy):
    def chunks(
        self,
        source: shared.Storage,
        options: shared.StrategyOptions,
    ) -> Iterable[dict[str, Any]]:
        return csv.DictReader(StringIO(source.read().decode("utf-8")))


@dataclasses.dataclass
class YukonGroupRecord(shared.Record):
    key_field = ""
    action_prefix = ""

    def transform(self, raw: Any):
        title = raw.get(self.key_field)
        name = _title_to_name(title)
        return {"title": title, "name": name}

    def ingest(self, context: types.Context) -> shared.IngestionResult:
        name = self.data["name"]
        topic = model.Group.get(name)

        action = self.action_prefix + (
            "update" if topic and self.options.get("update_existing") else "create"
        )
        if action == self.action_prefix + "update":
            self.data["id"] = topic.id

        result = tk.get_action(action)(context, self.data)

        return {
            "success": True,
            "result": result,
            "details": {"action": action},
        }


@dataclasses.dataclass
class YukonOrganizationRecord(YukonGroupRecord):
    key_field: str = "organization_title"
    action_prefix: str = "organization_"


@dataclasses.dataclass
class YukonTopicRecord(YukonGroupRecord):
    key_field: str = "topics"
    action_prefix: str = "group_"


@dataclasses.dataclass
class YukonPackageRecord(PackageRecord):
    def transform(self, raw: Any):
        data_dict = raw.copy()
        for key, value in DEFAULT_MAPPING.items():
            if not data_dict.get(key):
                data_dict[key] = value

        groups = [
            {"name": _title_to_name(t)}
            for t in (raw.get("topics") or "").split(",")
            if t
        ]
        tags = [
            {"name": munge.munge_tag(t)}
            for t in (raw.get("tags") or "").split(",")
            if t
        ]

        data_dict.update(
            {
                "name": self._generate_name(data_dict),
                "type": raw["schema_type"],
                "groups": groups,
                "tags": tags,
                "owner_org": _title_to_name(raw["organization_title"]),
            }
        )
        return data_dict

    def ingest(self, context: types.Context) -> shared.IngestionResult:
        if self.options.get("only_dates"):
            self._insert_dates()
            return {"success": True}
        result = super().ingest(context)
        redirect_map: RedirectMap = self.options.get("redirect_map")
        if redirect_map and (old_url := self.data.get("dkan_uri")):
            new_url = tk.h.url_for(
                result["result"]["type"] + ".read", id=result["result"]["name"]
            )
            redirect_map.add(old_url, new_url)
        self._insert_dates()
        return result

    def _generate_name(self, data_dict: dict[str, Any]) -> str:
        dkan_node_id = data_dict["dkan_node_id"]

        if pkg := (
            model.Session.query(model.Package)
            .filter(
                model.Package.extras.any(
                    and_(
                        model.PackageExtra.key == "dkan_node_id",
                        model.PackageExtra.value == str(dkan_node_id),
                    )
                )
            )
            .one_or_none()
        ):
            return pkg.name

        ideal_name = _title_to_name(data_dict["title"])
        pkg = model.Package.get(ideal_name)
        if not pkg or pkg.extras.get("dkan_node_id", "") == dkan_node_id:
            return ideal_name

        name_results = (
            model.Session.query(model.Package.name)
            .filter(model.Package.name.ilike(f"{ideal_name}%"))
            .all()
        )
        taken = {name_result[0] for name_result in name_results}
        counter = 1
        while True:
            candidate_name = ideal_name + "-" + str(counter)
            if candidate_name not in taken:
                return candidate_name
            counter = counter + 1
        return None

    def _insert_dates(self):
        pkg = model.Package.get(self.data["name"])
        pkg.metadata_created = datetime.strptime(
            self.data["metadata_created"], "%Y-%m-%d %H:%M:%S"
        )
        pkg.metadata_modified = datetime.strptime(
            self.data["metadata_modified"], "%Y-%m-%d %H:%M:%S"
        )
        model.Session.commit()


@dataclasses.dataclass
class YukonResourceRecord(ResourceRecord):
    def transform(self, raw: Any):
        data_dict = raw.copy()
        parent_dkan_node_id = data_dict["dkan_parent_dataset_node_id"]
        parent_pkg = (
            model.Session.query(model.Package)
            .filter(
                model.Package.extras.any(
                    and_(
                        model.PackageExtra.key == "dkan_node_id",
                        model.PackageExtra.value == str(parent_dkan_node_id),
                    )
                )
            )
            .one_or_none()
        )
        if not parent_pkg:
            log.exception("The parent package does not exist.")
            return {}

        unique_identifier = " ".join(
            [data_dict[key] for key in RESOURCE_UNIQUE_FIELD[data_dict["schema_type"]]]
        )
        data_dict.update(
            {
                "package_id": parent_pkg.id,
                "id": str(uuid.uuid3(RESOURCE_NS, str(unique_identifier))),
            }
        )

        if (data_dict.get("url_type") or "") == "upload":
            uploader = get_resource_uploader(data_dict)
            os.makedirs(uploader.get_directory(data_dict["id"]), exist_ok=True)
            while True:
                try:
                    response = requests.get(
                        requests.utils.requote_uri(self.raw["url"]),
                        headers=self.options["headers"],
                        cookies=self.options["cookies"],
                        timeout=20,
                    )
                    response.raise_for_status()
                    break
                except requests.exceptions.ReadTimeout as err:
                    log.warning(
                        "Read-timeout for %s (%s). Retrying in %s s",
                        self.raw["url"],
                        err,
                        RETRY_DELAY,
                    )
                except requests.exceptions.HTTPError as err:
                    status = err.response.status_code

                    if status == HTTPStatus.NOT_FOUND:
                        log.exception(
                            "Not found (%s): %s – giving up.",
                            status,
                            self.raw["url"],
                        )
                        data_dict["error"] = HTTPStatus.NOT_FOUND
                        break
                    log.warning(
                        "HTTP error %s for %s (%s). Retrying in %s s",
                        status,
                        self.raw["url"],
                        err,
                        RETRY_DELAY,
                    )
                except requests.exceptions.RequestException as err:
                    log.warning(
                        "Download failed for %s (%s). Retrying in %s s",
                        self.raw["url"],
                        err,
                        RETRY_DELAY,
                    )
                time.sleep(RETRY_DELAY)
            with open(uploader.get_path(data_dict["id"]), "wb") as f:
                f.write(response.content)
        return data_dict

    def ingest(self, context: types.Context) -> shared.IngestionResult:
        if error := self.data.get("error"):
            raise tk.ValidationError(error)

        result = super().ingest(context)
        redirect_map: RedirectMap = self.options.get("redirect_map")
        if redirect_map:
            if self.data.get("url_type") == "upload" and (
                old_file_url := self.data.get("url")
            ):
                new_file_url = result["result"]["url"]
                redirect_map.add(old_file_url, new_file_url)

            if old_resource_url := self.data.get("dkan_uri"):
                new_resource_url = tk.h.url_for(
                    "resource.read",
                    id=result["result"]["package_id"],
                    resource_id=result["result"]["id"],
                    _external=True,
                )
                redirect_map.add(old_resource_url, new_resource_url)

        self._insert_dates()
        return result

    def _insert_dates(self):
        res = model.Resource.get(self.data["name"])
        res.metadata_modified = datetime.strptime(
            self.data["last_modified"], "%Y-%m-%d %H:%M:%S"
        )
        model.Session.commit()


class YukonOrganizationStrategy(YukonCsvStrategy):
    record_factory = YukonOrganizationRecord


class YukonTopicStrategy(YukonCsvStrategy):
    record_factory = YukonTopicRecord


class YukonPackageStrategy(YukonCsvStrategy):
    record_factory = YukonPackageRecord


class YukonResourceStrategy(YukonCsvStrategy):
    record_factory = YukonResourceRecord


def _title_to_name(title: str) -> str:
    title = title.replace("–", "-")
    title = title.replace("&", "and")
    return munge.munge_title_to_name(title)
