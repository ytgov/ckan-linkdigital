from __future__ import annotations

import datetime as dt
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import click
import sqlalchemy as sa

from ckan import model
from ckan.lib import search

_COPY_RE = re.compile(r"^COPY\s+(?P<table>.+?)\s+\((?P<columns>.*)\)\s+FROM stdin;$")
MissingPackage = tuple[str, str]


@click.command("restore-metadata-modified", short_help="Restore dataset metadata_modified from a DB backup")
@click.argument("backup_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--dataset-ref",
    "dataset_refs",
    multiple=True,
    help="Optional live dataset id or name to process. Can be repeated.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview changes without writing to the database.",
)
@click.option(
    "--reindex/--no-reindex",
    default=False,
    show_default=True,
    help="Reindex changed datasets after the database update.",
)
def restore_metadata_modified(
    backup_path: Path,
    dataset_refs: tuple[str, ...],
    dry_run: bool,
    reindex: bool,
) -> None:
    """Restore live package.metadata_modified values from BACKUP_PATH.

    BACKUP_PATH must be a PostgreSQL custom-format dump containing the CKAN
    package table. Only package.metadata_modified is written to the live DB.
    """
    backup_dates = load_backup_package_dates(backup_path)
    click.echo(f"Loaded {len(backup_dates)} package date(s) from backup.")

    try:
        summary, changed_package_ids = restore_live_metadata_modified(
            backup_dates,
            dataset_refs=list(dataset_refs),
            dry_run=dry_run,
        )
    except Exception:
        model.Session.rollback()
        raise

    if reindex and changed_package_ids and not dry_run:
        reindex_packages(changed_package_ids)
        summary["reindexed"] = len(changed_package_ids)

    click.echo(
        f"restore-metadata-modified: scanned={summary['scanned']} matched={summary['matched']} "
        f"changed={summary['changed']} unchanged={summary['unchanged']} "
        f"missing={len(summary['missing'])} reindexed={summary['reindexed']} dry_run={dry_run}"
    )

    if summary["missing"]:
        report_path = write_missing_packages_report(summary["missing"])
        click.echo(f"Datasets missing from backup report: {report_path}")


def load_backup_package_dates(backup_path: Path) -> dict[str, dt.datetime]:
    """Load package metadata_modified values from a PostgreSQL custom dump."""
    dump = _restore_package_table_dump(backup_path)
    return parse_package_dates_from_dump(dump)


def parse_package_dates_from_dump(dump: str) -> dict[str, dt.datetime]:
    """Parse package dates from a text dump containing COPY package data."""
    backup_dates: dict[str, dt.datetime] = {}
    copy_columns: list[str] | None = None

    for line in dump.splitlines():
        if copy_columns is None:
            match = _COPY_RE.match(line)
            if not match or not _is_package_table(match.group("table")):
                continue

            copy_columns = _split_copy_columns(match.group("columns"))
            _validate_copy_columns(copy_columns)
            continue

        if line == r"\.":
            copy_columns = None
            continue

        row = dict(zip(copy_columns, _decode_copy_row(line), strict=False))
        package_id = _required_copy_value(row, "id")
        backup_dates[package_id] = _parse_metadata_modified(_required_copy_value(row, "metadata_modified"))

    if not backup_dates:
        raise click.ClickException("No package metadata_modified rows were found in the backup dump.")

    return backup_dates


def restore_live_metadata_modified(
    backup_dates: dict[str, dt.datetime],
    *,
    dataset_refs: list[str] | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """Restore metadata_modified values for live packages."""
    scanned = 0
    matched = 0
    changed = 0
    unchanged = 0
    missing: list[MissingPackage] = []
    changed_package_ids: list[str] = []

    for package_id, name, metadata_modified in _live_package_rows(dataset_refs):
        scanned += 1
        backup_date = backup_dates.get(package_id)

        if backup_date is None:
            missing.append((name, package_id))
            continue

        matched += 1

        if _same_datetime(metadata_modified, backup_date):
            unchanged += 1
            continue

        changed += 1
        changed_package_ids.append(package_id)

        if not dry_run:
            _update_package_metadata_modified(package_id, backup_date)
    if not dry_run:
        model.repo.commit()

    summary = {
        "scanned": scanned,
        "matched": matched,
        "changed": changed,
        "unchanged": unchanged,
        "missing": missing,
        "reindexed": 0,
    }

    return summary, changed_package_ids


def reindex_packages(package_ids: list[str]) -> None:
    """Reindex changed packages so Solr reflects restored dates."""
    search.rebuild(package_ids=package_ids, defer_commit=True, force=False, quiet=True)
    search.commit()


def write_missing_packages_report(missing_packages: list[MissingPackage]) -> Path:
    """Write missing package ids/names to a text report in /tmp."""
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir="/tmp",
        prefix="yukon-metadata-modified-missing-",
        suffix=".txt",
    ) as report:
        report.write("name\tid\n")
        for name, package_id in missing_packages:
            report.write(f"{name}\t{package_id}\n")
        return Path(report.name)


def _restore_package_table_dump(backup_path: Path) -> str:
    command = [
        "pg_restore",
        "--data-only",
        "--table=package",
        "--file=-",
        str(backup_path),
    ]

    try:
        result = subprocess.run(  # noqa: S603
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise click.ClickException(
            "Could not find 'pg_restore'. Install PostgreSQL client tools and make sure pg_restore is in PATH."
        ) from exc

    if result.returncode:
        stderr = result.stderr.strip()
        message = f"pg_restore failed with exit code {result.returncode}."
        if stderr:
            message = f"{message}\n{stderr}"
        raise click.ClickException(message)

    return result.stdout


def _live_package_rows(dataset_refs: list[str] | None) -> list[tuple[str, str, dt.datetime]]:
    query = model.Session.query(
        model.Package.id,
        model.Package.name,
        model.Package.metadata_modified,
    )

    query = query.filter(model.Package.state != model.State.DELETED)

    if dataset_refs:
        query = query.filter(
            sa.or_(
                model.Package.id.in_(dataset_refs),
                model.Package.name.in_(dataset_refs),
            )
        )

    return query.order_by(model.Package.name).all()


def _update_package_metadata_modified(package_id: str, metadata_modified: dt.datetime) -> None:
    statement = (
        model.package_table.update()
        .where(model.package_table.c.id == package_id)
        .values(metadata_modified=metadata_modified)
    )
    model.Session.execute(statement)


def _is_package_table(table_name: str) -> bool:
    normalized = table_name.replace('"', "").lower()
    return normalized == "package" or normalized.endswith(".package")


def _split_copy_columns(columns: str) -> list[str]:
    result: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0

    while index < len(columns):
        char = columns[index]
        if char == '"':
            if quoted and index + 1 < len(columns) and columns[index + 1] == '"':
                current.append('"')
                index += 2
                continue
            quoted = not quoted
        elif char == "," and not quoted:
            result.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1

    result.append("".join(current).strip())
    return result


def _validate_copy_columns(columns: list[str]) -> None:
    missing = {"id", "metadata_modified"} - set(columns)
    if missing:
        raise click.ClickException("The package COPY data is missing required column(s): " + ", ".join(sorted(missing)))


def _decode_copy_row(line: str) -> list[str | None]:
    return [_decode_copy_field(field) for field in line.split("\t")]


def _decode_copy_field(value: str) -> str | None:
    if value == r"\N":
        return None

    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        if index + 1 >= len(value):
            result.append("\\")
            index += 1
            continue

        next_char = value[index + 1]
        escapes = {
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
            "\\": "\\",
        }
        if next_char in escapes:
            result.append(escapes[next_char])
            index += 2
            continue

        if next_char in "01234567":
            end = index + 1
            while end < len(value) and end < index + 4 and value[end] in "01234567":
                end += 1
            result.append(chr(int(value[index + 1 : end], 8)))
            index = end
            continue

        result.append(next_char)
        index += 2

    return "".join(result)


def _required_copy_value(row: dict[str, str | None], key: str) -> str:
    value = row.get(key)
    if value is None:
        raise click.ClickException(f"Package COPY row has a null {key} value.")
    return value


def _parse_metadata_modified(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise click.ClickException(f"Invalid metadata_modified value in backup: {value!r}") from exc

    if parsed.tzinfo:
        return parsed.astimezone(dt.UTC).replace(tzinfo=None)
    return parsed


def _same_datetime(current: Any, backup: dt.datetime) -> bool:
    if not isinstance(current, dt.datetime):
        return False

    current_normalized = current
    if current_normalized.tzinfo:
        current_normalized = current_normalized.astimezone(dt.UTC).replace(tzinfo=None)

    return current_normalized == backup
