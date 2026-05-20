"""CLI commands for ckanext-yukon.

Commands added to `__all__` attribute are added to main CKAN CLI.

Example:
    ```sh
    ckan yukon --help
    ```
"""

from __future__ import annotations

import click

from ckan import model
from ckan.cli import load_config
from ckan.config.middleware import make_app

from ckanext.yukon import matomo_sync, matomo_traffic
from ckanext.yukon.cli.metadata_modified import restore_metadata_modified
from ckanext.yukon.cli.migration import data_migration

__all__ = ["yukon", "yukon_matomo"]


# Register CLI group. Code of the group is executed whenever subcommand of this
# group is invoked. Usually, group body remains empty. But if all subcommands
# contain identical initialization process, consider describing it inside
# group.
@click.group(short_help="yukon CLI.")
@click.pass_context
def yukon(ctx: click.Context):
    """CLI commands of yukon plugin."""
    ctx.meta["yukon"] = "yukon"


yukon.add_command(data_migration)
yukon.add_command(restore_metadata_modified)


# Command decorated with `yukon.command()` decorator is
# registered inside the group. Name of the command matches name of the function
# with underscores replaced by hyphens. You can pass string into `.command()`
# to use a different name of the command.
#
# `click.argument` defines positional argument of the command. `click.option`
# defines optional flag with the specified short and long names.
#
# `click.pass_context` passes shared contex object to the command. Example
# below uses it to read data set by initialization code from group body.
@yukon.command()
@click.argument("name", default="yukon")
@click.option("-v", "--verbose", count=True, help="Increase verbosity")
@click.pass_context
def command(ctx: click.Context, name: str, verbose: int):
    """Nunc porta vulputate tellus."""
    msg = f"Hello, {name or ctx.meta['yukon']}"
    if verbose:
        msg += "!" * verbose

    click.echo(msg)


# Command can execute arbitrary code. If you are writing command that processes
# a lot of records, wrap iteration over records into `click.progressbar`. It
# results in progressbar that shows estimated time required to complete the command.
#
# When printing something, always use `click.echo` for plain output and
# `click.secho` for styled(colored) output. Never use built-in `print`
# function. It's allowed to use logging, but most likely, you don't need and
# `click.echo` is much better choice.
@yukon.command()
def count_users():
    """Iterate over users and count something."""
    q = model.Session.query(model.User)
    total = 0

    with click.progressbar(q, q.count()) as bar:
        for _user in bar:
            total += 1

    click.secho(f"Result: {click.style(total, bold=True)}!")


@click.group(name="yukon-matomo")
@click.help_option("-h", "--help")
@click.pass_context
def yukon_matomo(ctx: click.Context):
    config_dict = load_config()
    flask_app = make_app(config_dict)._wsgi_app
    ctx.obj = {"flask_app": flask_app}


@yukon_matomo.command("sync-usage-data", short_help="Sync usage_data from Matomo")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview updates without writing to DB.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of datasets for this run.",
)
@click.option(
    "--offset",
    type=int,
    default=None,
    help="Skip this many datasets before processing the batch.",
)
@click.option(
    "--dataset-ref",
    "dataset_refs",
    multiple=True,
    help="Optional dataset name or id. Can be passed multiple times.",
)
@click.pass_context
def sync_usage_data(ctx: click.Context, dry_run: bool, limit: int | None, offset: int | None, dataset_refs: list[str]):
    """Sync usage_data extras from Matomo without metadata updates."""
    flask_app = ctx.obj["flask_app"]
    with flask_app.app_context():
        summary = matomo_sync.sync_usage_data(
            dry_run=dry_run,
            limit=limit,
            offset=offset,
            dataset_refs=list(dataset_refs) if dataset_refs else None,
        )

    click.echo(
        "sync-usage-data: processed={processed} updated={updated} "
        "skipped={skipped} failed={failed} dry_run={dry_run} "
        "offset={offset} total={total} has_more={has_more} "
        "next_offset={next_offset}".format(**summary)
    )


@yukon_matomo.command(
    "generate-test-traffic",
    short_help="Generate fake Matomo visits/downloads for one dataset",
)
@click.option(
    "--dataset-ref",
    required=True,
    help="Dataset name or id to target.",
)
@click.option(
    "--visits-3y",
    "visits_3y",
    type=int,
    default=25,
    show_default=True,
    help=("Pageviews with random timestamps in the 3-year window (older than 90 days)."),
)
@click.option(
    "--visits-90d",
    "visits_90d",
    type=int,
    default=10,
    show_default=True,
    help="Pageviews with random timestamps in the last 90 days.",
)
@click.option(
    "--downloads-3y",
    "downloads_3y",
    type=int,
    default=10,
    show_default=True,
    help=("Download events with random timestamps in the 3-year window (older than 90 days)."),
)
@click.option(
    "--downloads-90d",
    "downloads_90d",
    type=int,
    default=5,
    show_default=True,
    help="Download events with random timestamps in the last 90 days.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be emitted without sending events.",
)
@click.pass_context
def generate_test_traffic(
    ctx: click.Context,
    dataset_ref: str,
    visits_3y: int,
    visits_90d: int,
    downloads_3y: int,
    downloads_90d: int,
    dry_run: bool,
):
    """Emit synthetic Matomo traffic spread across 3-year and 90-day windows.

    Each pageview is sent with a unique visitor ID so Matomo counts it
    as a distinct visit.  The cdt (custom datetime) parameter backdates
    events so the 3-year and 90-day sync totals will diff correctly.
    """
    flask_app = ctx.obj["flask_app"]
    with flask_app.app_context():
        summary = matomo_traffic.generate_test_traffic(
            dataset_ref=dataset_ref,
            visits_3y=visits_3y,
            visits_90d=visits_90d,
            downloads_3y=downloads_3y,
            downloads_90d=downloads_90d,
            dry_run=dry_run,
        )

    click.echo(
        "generate-test-traffic: dataset={dataset}\n"
        "  visits    3y={visits_3y_sent}/{visits_3y_targeted}"
        "  90d={visits_90d_sent}/{visits_90d_targeted}\n"
        "  downloads 3y={downloads_3y_sent}/{downloads_3y_targeted}"
        "  90d={downloads_90d_sent}/{downloads_90d_targeted}\n"
        "  dry_run={dry_run}".format(**summary)
    )


@yukon_matomo.command(
    "generate-bulk-traffic",
    short_help="Generate fake Matomo traffic for all datasets of all types",
)
@click.option(
    "--visits-3y",
    "visits_3y",
    type=int,
    default=25,
    show_default=True,
    help="Pageviews per dataset backdated to the 3-year window (older than 90 days).",
)
@click.option(
    "--visits-90d",
    "visits_90d",
    type=int,
    default=10,
    show_default=True,
    help="Pageviews per dataset backdated to the last 90 days.",
)
@click.option(
    "--downloads-3y",
    "downloads_3y",
    type=int,
    default=10,
    show_default=True,
    help="Download events per dataset backdated to the 3-year window.",
)
@click.option(
    "--downloads-90d",
    "downloads_90d",
    type=int,
    default=5,
    show_default=True,
    help="Download events per dataset backdated to the last 90 days.",
)
@click.option(
    "--dataset-ref",
    "dataset_refs",
    multiple=True,
    help=("Restrict to specific dataset name/id. Can be repeated. Omit to target all supported datasets."),
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Process at most this many datasets.",
)
@click.option(
    "--offset",
    type=int,
    default=None,
    help="Skip this many datasets before starting.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be sent without emitting any events.",
)
@click.pass_context
def generate_bulk_traffic(
    ctx: click.Context,
    visits_3y: int,
    visits_90d: int,
    downloads_3y: int,
    downloads_90d: int,
    dataset_refs: list[str],
    limit: int | None,
    offset: int | None,
    dry_run: bool,
):
    """Generate fake Matomo traffic for every active dataset of every type.

    Iterates all datasets of types: data, information, access-requests,
    pia-summaries.  Events are spread across two windows:

    \b
      3-year window  — random timestamps older than 90 days
      90-day window  — random timestamps within the last 90 days

    Each pageview uses a unique visitor ID so Matomo counts it as a
    distinct visit.  Datasets without resources get their download counts
    set to 0 automatically.
    """
    flask_app = ctx.obj["flask_app"]
    with flask_app.app_context():
        summary = matomo_traffic.generate_bulk_traffic(
            visits_3y=visits_3y,
            visits_90d=visits_90d,
            downloads_3y=downloads_3y,
            downloads_90d=downloads_90d,
            dataset_refs=list(dataset_refs) if dataset_refs else None,
            limit=limit,
            offset=offset,
            dry_run=dry_run,
        )

    click.echo(
        "generate-bulk-traffic: total={total_packages} "
        "succeeded={succeeded} failed={failed} skipped={skipped} "
        "dry_run={dry_run}\n"
        "  visits    3y={visits_3y_sent}  90d={visits_90d_sent}\n"
        "  downloads 3y={downloads_3y_sent}  90d={downloads_90d_sent}".format(**summary)
    )
