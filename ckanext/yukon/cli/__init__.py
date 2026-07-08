from __future__ import annotations

import click

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
