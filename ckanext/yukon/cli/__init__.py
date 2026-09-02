from __future__ import annotations

from itertools import pairwise
from typing import Any

import click
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.lib.search import rebuild

from ckanext.activity.model import Activity

from ckanext.yukon.cli.metadata_modified import restore_metadata_modified
from ckanext.yukon.cli.migration import data_migration

from .matomo import yukon_matomo

__all__ = ["yukon", "yukon_matomo"]


# Register CLI group. Code of the group is executed whenever subcommand of this
# group is invoked. Usually, group body remains empty. But if all subcommands
# contain identical initialization process, consider describing it inside
# group.
@click.group(short_help="Yukon CLI.")
@click.pass_context
def yukon(ctx: click.Context):
    """CLI commands of yukon plugin."""
    ctx.meta["yukon"] = "yukon"


yukon.add_command(data_migration)
yukon.add_command(restore_metadata_modified)


@yukon.group()
def maintain():
    """Portal maintenance commands."""


@maintain.command()
def drop_downloadall():
    """Remove pre-computed dataset archives.

    This command is a part of migration to FPX. Can be removed after
    YUKONXCIAA-45 deployment.

    """
    stmt = sa.select(model.Resource).where(
        sa.cast(model.Resource.extras, JSONB).has_key("downloadall_metadata_modified")
    )

    total = model.Session.scalar(stmt.with_only_columns(sa.func.count()))
    click.echo(f"Found {total} resources created by downloadall extension")
    if not total:
        click.secho("Done", fg="green")
        return

    if click.confirm("Show these resources?"):
        for res in model.Session.scalars(stmt):
            url = tk.url_for("dataset_resource.read", id=res.package_id, resource_id=res.id, _external=True)
            click.echo(f"ID: {res.id}\tURL: {url}")

    if click.confirm("Remove these resources?"):
        pkg_ids = set(model.Session.scalars(stmt.with_only_columns(model.Resource.package_id)))

        delete_stmt = sa.delete(model.Resource).where(model.Resource.id.in_(stmt.with_only_columns(model.Resource.id)))
        model.Session.execute(delete_stmt)
        model.Session.commit()

        for pkg in pkg_ids:
            rebuild(pkg)

    click.secho("Done", fg="green")


@maintain.command()
def fix_resource_order():
    """Restore resoruce order field to allow creation oof new resources.

    This command is a part of v2.12 upgrade. Remove it after YUKONXCIAA-45 deployment.

    """
    stmt = sa.select(
        model.Resource,
        sa.func.row_number().over(order_by=model.Resource.position, partition_by=model.Resource.package_id) - 1,
    ).order_by(model.Resource.package_id.asc(), model.Resource.position.asc())

    pkg_ids: set[str] = set()
    for res, rank in model.Session.execute(stmt):
        if res.position != rank:
            res.position = rank
            pkg_ids.add(res.package_id)
            model.Session.commit()
    for pkg_id in pkg_ids:
        rebuild(pkg_id)


@maintain.command()
def clear_stream():
    """Remove flood activities created by downloadall extension.

    This command is a part of v2.12 upgrade. Remove it after YUKONXCIAA-47 deployment.
    """
    pkg_stmt = sa.select(Activity.object_id.distinct()).where(
        Activity.activity_type.in_(["changed package", "new package"])
    )

    total = model.Session.scalar(pkg_stmt.with_only_columns(sa.func.count(Activity.object_id.distinct()))) or 0
    ids = model.Session.scalars(pkg_stmt).fetchall()
    with click.progressbar(ids, length=total) as bar:
        for idx, pkg_id in enumerate(bar, 1):
            stmt = (
                sa.select(Activity)
                .where(Activity.object_id == pkg_id, Activity.activity_type.in_(["changed package", "new package"]))
                .order_by(Activity.timestamp)
            )
            bar.label = f"[{idx} / {total}]Updating package {pkg_id}"

            for prev, cur in pairwise(model.Session.scalars(stmt)):
                first: dict[str, Any] = prev.data["package"]
                second: dict[str, Any] = cur.data["package"]
                if not first or not second:
                    continue

                if first.keys() != second.keys():
                    continue

                keys = first.keys() - {"metadata_modified", "resources"}
                if any(first[key] != second[key] for key in keys):
                    continue

                first_resources = [res for res in first["resources"] if not res.get("downloadall_datapackage_hash")]
                second_resources = [res for res in second["resources"] if not res.get("downloadall_datapackage_hash")]
                if first_resources != second_resources:
                    continue

                model.Session.delete(cur)

            model.Session.commit()
