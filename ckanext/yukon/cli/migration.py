from __future__ import annotations

import io
import logging
import mimetypes
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import click
from werkzeug.datastructures import FileStorage

import ckan.plugins.toolkit as tk

from ckanext.yukon.ingest import RedirectMap

log = logging.getLogger(__name__)

VALID_ENTITIES = [
    "organizations",
    "topics",
    "information",
    "data",
    "pia_summaries",
    "access_requests",
    "resources_data",
    "resources_access_requests",
    "resources_information",
]

ENTITY_STRATEGIES = {
    "organizations": "yukon:organization",
    "topics": "yukon:topic",
    "information": "yukon:package",
    "data": "yukon:package",
    "pia_summaries": "yukon:package",
    "access_requests": "yukon:package",
    "resources_data": "yukon:resource",
    "resources_access_requests": "yukon:resource",
    "resources_information": "yukon:resource",
}

RESOURCE_TO_PACKAGE = {
    "resources_information": "information",
    "resources_data": "data",
    "resources_access_requests": "access_requests",
}

REDIRECT_MAP_REQUIRED = [
    "information",
    "data",
    "access_requests",
    "resources_information",
    "resources_data",
    "resources_access_requests",
]


@click.group("data-migration", short_help="Migrate DKAN data")
@click.help_option("-h", "--help")
def data_migration():
    pass


class InvalidZip(click.ClickException):
    def __init__(self, path: str, err: Exception) -> None:
        super().__init__(f"{path} is not a valid ZIP: {err}")


class MissingFiles(click.ClickException):
    def __init__(self, filenames: Iterable[str]) -> None:
        files = ", ".join(filenames)
        super().__init__(f"Missing CSV files: {files}")


class IngestFailures(click.ClickException):
    def __init__(self, failures: list[str]) -> None:
        msg = f"Finished with {len(failures)} failure(s): {', '.join(failures)}"
        super().__init__(msg)


def parse_header(
    ctx: click.Context, _param: click.Option, value: tuple[str, ...]
) -> dict[str, str]:
    """Turn multiple ``--header "Key: Value"`` into a dict."""
    headers: dict[str, str] = {}
    for item in value:
        if ":" not in item:
            raise click.BadParameter(  # noqa: TRY003
                'Header must be "Key: Value"', ctx=ctx, param=_param
            )
        key, val = item.split(":", 1)
        headers[key.strip()] = val.strip()
    return headers


def parse_cookie(
    ctx: click.Context, _param: click.Option, value: tuple[str, ...]
) -> dict[str, str]:
    """Turn multiple ``--cookie k=v`` into a dict."""
    cookies: dict[str, str] = {}
    for item in value:
        if "=" not in item:
            raise click.BadParameter(  # noqa: TRY003
                'Cookie must be "key=value"', ctx=ctx, param=_param
            )
        key, val = item.split("=", 1)
        cookies[key.strip()] = val.strip()
    return cookies


@data_migration.command("run")
@click.argument("zip_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-e",
    "--entity",
    type=click.Choice(VALID_ENTITIES),
    multiple=True,
    help="Names of entities to migrate",
)
@click.option(
    "-H",
    "--header",
    multiple=True,
    callback=parse_header,
    help='Extra HTTP header (repeatable), e.g.  -H "User-Agent: mybot/1.0"',
)
@click.option(
    "-c",
    "--cookie",
    multiple=True,
    callback=parse_cookie,
    help='Cookie (repeatable), e.g.  -c "cf_clearance=abc123"',
)
@click.option(
    "-s",
    "--skip",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Number of records to skip before ingesting (per CSV).",
)
@click.option(
    "-t",
    "--take",
    type=click.IntRange(min=1),
    default=None,
    help="Maximum number of records to ingest from each CSV (after --skip).",
)
@click.option(
    "-o",
    "--redirect-map-path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default="redirect.map",
    show_default=True,
    help="File to write Nginx redirect map.",
)
@click.option(
    "-d",
    "--update-resource-dates-only",
    is_flag=True,
    default=False,
    help="Update only resource metadata dates (only applicable to resource entities).",
)
def migrate_data(  # noqa PLR0913
    zip_path: str,
    entity: tuple[str, ...],
    header: dict[str, str],
    cookie: dict[str, str],
    skip: int,
    take: int | None,
    redirect_map_path: Path,
    update_resource_dates_only: bool,
):
    """Import CSVs packed in *zip_path* using CKAN’s ``ingest_import_records``.

    The ZIP **must** contain ``<entity>.csv`` for every selected or default
    entity.
    """
    redirect_map = RedirectMap()
    selected = [e.lower() for e in (entity or VALID_ENTITIES)]
    ordered = [e for e in VALID_ENTITIES if e in selected]

    user = tk.get_action("get_site_user")({"ignore_auth": True}, {})

    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as err:
        raise InvalidZip(zip_path, err) from err

    failures: list[str] = []
    with archive, tempfile.TemporaryDirectory():
        members = {Path(m).name.lower(): m for m in archive.namelist()}

        missing = [f"{e}.csv" for e in ordered if f"{e}.csv" not in members]
        if missing:
            raise MissingFiles(missing)

        resources_ran: set[str] = set()

        for ent in ordered:
            member = members[f"{ent}.csv"]
            with archive.open(member) as src:
                file_storage = FileStorage(
                    stream=io.BytesIO(src.read()),
                    filename=Path(member).name,
                    content_type=mimetypes.guess_type(member)[0] or "text/csv",
                )

            options = {
                "record_options": {
                    "update_existing": True,
                    "cookies": cookie,
                    "headers": header,
                    "update_resource_dates_only": update_resource_dates_only,
                },
            }

            if ent in REDIRECT_MAP_REQUIRED:
                options["record_options"]["redirect_map"] = redirect_map

            try:
                tk.get_action("ingest_import_records")(
                    {"user": user["name"]},
                    {
                        "strategy": ENTITY_STRATEGIES[ent],
                        "source": file_storage,
                        "report": "tmp",
                        "skip": skip,
                        "take": take,
                        "options": options,
                    },
                )
                click.secho(f"Imported {ent}", fg="green")
                if ent in RESOURCE_TO_PACKAGE:
                    resources_ran.add(ent)

            except tk.ValidationError as err:
                log.exception("Import failed for %s", ent)
                click.secho(f"Failed {ent}: {err}", fg="red")
                failures.append(ent)

        if update_resource_dates_only:
            click.secho("Resource dates have been updated.", fg="green")
            return

        # packages that need a dates upgrade only if their resource ran
        for resource_ent in resources_ran:
            package_ent = RESOURCE_TO_PACKAGE[resource_ent]
            member = members[f"{package_ent}.csv"]

            with archive.open(member) as src:
                file_storage = FileStorage(
                    stream=io.BytesIO(src.read()),
                    filename=Path(member).name,
                    content_type=mimetypes.guess_type(member)[0] or "text/csv",
                )

            try:
                tk.get_action("ingest_import_records")(
                    {"user": user["name"]},
                    {
                        "strategy": "yukon:package",
                        "source": file_storage,
                        "report": "tmp",
                        "options": {
                            "record_options": {
                                "update_existing": True,
                                "only_dates": True,
                            },
                        },
                    },
                )
                click.secho(f"Package dates upgraded for {package_ent}", fg="cyan")
            except tk.ValidationError as err:
                log.exception("Date-upgrade import failed for %s", package_ent)
                click.secho(f"Date-upgrade failed {package_ent}: {err}", fg="red")
                failures.append(f"{package_ent} (dates-upgrade)")

    if failures:
        raise IngestFailures(failures)

    click.secho("All selected entities imported successfully.", fg="green")
    redirect_map.write(redirect_map_path)
    click.secho(f"Wrote {redirect_map}", fg="blue")
