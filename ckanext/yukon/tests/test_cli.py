"""Tests for ckanext.yukon.cli module.

Use `cli` fixture to invoke CLI commands.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from faker import Faker

from ckan import model
from ckan.tests import factories

import ckanext.yukon.cli as commands
from ckanext.yukon.cli import metadata_modified as metadata_modified_cli


class TestCommand:
    """Test `heh command` CLI command."""

    def test_output(self, cli: CliRunner, faker: Faker):
        """Command prints expected message."""
        # it's possible to execute `commands.command` directly, but group
        # contains initialization logic and `commands.command` will fail
        # without it
        #
        # Any parameter specified after the command must be passed inside a
        # second argument of `cli.invoke`. For example, `yukon
        # a b -C 1 --xxx=2` becomes `cli.invoke(yukon, ["a",
        # "b", "-C", "1", "--xxx=2"])`
        result = cli.invoke(commands.yukon, ["command"])
        # `result.exit_code` contains `0` if command succeeded
        assert not result.exit_code
        # `result.output` contains normal output. `result.stderr` contains
        # output of an error
        assert result.output == "Hello, yukon\n"

        # use fake data instead of hardcoded test values to discover
        # output-based problems
        name = faker.word()
        result = cli.invoke(commands.yukon, ["command", name])
        assert result.output == f"Hello, {name}\n"

    def test_verbosity(self, cli: CliRunner):
        """Verbosity level appends exclamation marks."""
        result = cli.invoke(commands.yukon, ["command", "-v"])
        assert result.output == "Hello, yukon!\n"

        result = cli.invoke(commands.yukon, ["command", "-vvv"])
        assert result.output == "Hello, yukon!!!\n"


class TestCountUsers:
    """Test `heh count-users` CLI command."""

    def test_output(self, cli: CliRunner, faker: Faker, user_factory: Any):
        """Command counts number of users in DB."""
        result = cli.invoke(commands.yukon, ["count-users"])
        count = model.User.count()
        assert result.output == f"\nResult: {count}!\n"

        # create a new user to verify that we are not receiving static result
        user_factory()

        result = cli.invoke(commands.yukon, ["count-users"])
        count = model.User.count()
        assert result.output == f"\nResult: {count}!\n"


class TestRestoreMetadataModified:
    """Test `yukon restore-metadata-modified` CLI command."""

    def test_parse_package_dates_from_copy_dump(self):
        """Package dates are parsed from pg_restore COPY output."""
        dump = "\n".join(
            [
                "SET statement_timeout = 0;",
                "COPY public.package (id, name, metadata_created, metadata_modified, state) FROM stdin;",
                "pkg-1\tdataset-one\t2024-01-01 00:00:00\t2024-02-03 04:05:06.123456\tactive",
                r"\.",
                "",
            ]
        )

        backup_dates = metadata_modified_cli.parse_package_dates_from_dump(dump)

        assert backup_dates["pkg-1"] == dt.datetime(2024, 2, 3, 4, 5, 6, 123456)

    @pytest.mark.usefixtures("with_plugins", "clean_db")
    def test_updates_only_metadata_modified(self, cli: CliRunner, tmp_path: Any, monkeypatch: Any):
        """Live package dates are restored and missing backup rows are reported."""
        current_date = dt.datetime(2026, 5, 19, 12, 0, 0)
        backup_date = dt.datetime(2025, 4, 18, 9, 30, 0)
        missing_date = dt.datetime(2026, 5, 19, 13, 0, 0)

        package = _create_package("restore-target", current_date)
        missing_package = _create_package("not-in-backup", missing_date)
        backup_path = tmp_path / "backup.dump"
        backup_path.write_text("placeholder")

        monkeypatch.setattr(
            metadata_modified_cli,
            "load_backup_package_dates",
            lambda _backup_path: {package.id: backup_date},
        )

        result = cli.invoke(commands.yukon, ["restore-metadata-modified", str(backup_path)])

        assert result.exit_code == 0, result.output
        assert "changed=1" in result.output
        assert "missing=1" in result.output
        assert f"{missing_package.name} ({missing_package.id})" not in result.output

        report_path = _missing_report_path(result.output)
        assert report_path.parent == Path("/tmp")
        assert f"{missing_package.name}\t{missing_package.id}" in report_path.read_text()

        model.Session.expire_all()
        assert model.Package.get(package.id).metadata_modified == backup_date
        assert model.Package.get(missing_package.id).metadata_modified == missing_date

    @pytest.mark.usefixtures("with_plugins", "clean_db")
    def test_dry_run_does_not_update(self, cli: CliRunner, tmp_path: Any, monkeypatch: Any):
        """Dry-run reports pending changes without writing them."""
        current_date = dt.datetime(2026, 5, 19, 12, 0, 0)
        backup_date = dt.datetime(2025, 4, 18, 9, 30, 0)

        package = _create_package("dry-run-target", current_date)
        backup_path = tmp_path / "backup.dump"
        backup_path.write_text("placeholder")

        monkeypatch.setattr(
            metadata_modified_cli,
            "load_backup_package_dates",
            lambda _backup_path: {package.id: backup_date},
        )

        result = cli.invoke(commands.yukon, ["restore-metadata-modified", str(backup_path), "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "changed=1" in result.output

        model.Session.expire_all()
        assert model.Package.get(package.id).metadata_modified == current_date


def _create_package(name: str, metadata_modified: dt.datetime) -> model.Package:
    organization = factories.Organization()
    package = factories.Dataset.model(name=name, title=name, owner_org=organization["id"])
    package.metadata_modified = metadata_modified
    model.Session.commit()
    return package


def _missing_report_path(output: str) -> Path:
    match = re.search(r"Datasets missing from backup report: (?P<path>/tmp/\S+\.txt)", output)
    assert match, output
    return Path(match.group("path"))
