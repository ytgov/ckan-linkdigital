from __future__ import annotations

import csv
import dataclasses
import logging
import os
import uuid
from datetime import datetime
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

log = logging.getLogger(__name__)

HTTP_OK = 200
RESOURCE_NS = uuid.uuid3(uuid.NAMESPACE_DNS, "yukon_resource")

DEFAULT_MAPPING = {
    "notes": "not_specified",
    "internal_contact_name": "not_specified",
    "internal_contact_email": "not_specified",
    "response_type": "not_specified",
}

RESOURCE_UNIQUE_FIELD = {
    "information": ["dkan_resource_node_id"],
    "data": ["dkan_resource_node_id"],
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
        if not pkg or pkg.extras["dkan_node_id"] == dkan_node_id:
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
        parent_dcan_node_id = data_dict["dkan_parent_dataset_node_id"]
        parent_pkg = (
            model.Session.query(model.Package)
            .filter(
                model.Package.extras.any(
                    and_(
                        model.PackageExtra.key == "dkan_node_id",
                        model.PackageExtra.value == str(parent_dcan_node_id),
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
            with open(uploader.get_path(data_dict["id"]), "wb") as f:
                response = requests.get(
                    self.raw["url"],
                    headers=self.options["headers"],
                    cookies=self.options["cookies"],
                    timeout=20,
                )
                if response.status_code != HTTP_OK:
                    log.exception("Cannot download resource file.")
                    return data_dict
                f.write(response.content)
        return data_dict

    def ingest(self, context: types.Context) -> shared.IngestionResult:
        result = super().ingest(context)
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
