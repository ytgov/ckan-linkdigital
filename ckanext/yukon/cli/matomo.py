from __future__ import annotations

import click

from ckanext.yukon import matomo_sync, matomo_traffic


@click.group(short_help="Matomo analytics management.")
def yukon_matomo():
    """Matomo analytics management."""


@yukon_matomo.command(short_help="Sync usage_data from Matomo")
@click.option("--dry-run", is_flag=True, help="Preview updates without writing to DB.")
@click.option("--limit", type=int, default=None, help="Limit number of datasets for this run.")
@click.option("--offset", type=int, default=None, help="Skip this many datasets before processing the batch.")
@click.option("--dataset-ref", multiple=True, help="Optional dataset name or id. Can be passed multiple times.")
def sync_usage_data(dry_run: bool, limit: int | None, offset: int | None, dataset_ref: tuple[str]):
    """Sync usage_data extras from Matomo without metadata updates."""
    summary = matomo_sync.sync_usage_data(
        dry_run=dry_run,
        limit=limit,
        offset=offset,
        dataset_refs=list(dataset_ref) if dataset_ref else None,
    )

    click.echo(
        "sync-usage-data: processed={processed} updated={updated} "
        "skipped={skipped} failed={failed} dry_run={dry_run} "
        "offset={offset} total={total} has_more={has_more} "
        "next_offset={next_offset}".format(**summary)
    )


@yukon_matomo.command(short_help="Generate fake Matomo visits/downloads for one dataset")
@click.option("--dataset-ref", required=True, help="Dataset name or id to target.")
@click.option(
    "--visits-3y",
    type=int,
    default=25,
    show_default=True,
    help="Pageviews with random timestamps in the 3-year window (older than 90 days).",
)
@click.option(
    "--visits-90d",
    type=int,
    default=10,
    show_default=True,
    help="Pageviews with random timestamps in the last 90 days.",
)
@click.option(
    "--downloads-3y",
    type=int,
    default=10,
    show_default=True,
    help="Download events with random timestamps in the 3-year window (older than 90 days).",
)
@click.option(
    "--downloads-90d",
    type=int,
    default=5,
    show_default=True,
    help="Download events with random timestamps in the last 90 days.",
)
@click.option("--dry-run", is_flag=True, help="Show what would be emitted without sending events.")
def generate_test_traffic(
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


@yukon_matomo.command(short_help="Generate fake Matomo traffic for all datasets of all types")
@click.option(
    "--visits-3y",
    type=int,
    default=25,
    show_default=True,
    help="Pageviews per dataset backdated to the 3-year window (older than 90 days).",
)
@click.option(
    "--visits-90d", type=int, default=10, show_default=True, help="Pageviews per dataset backdated to the last 90 days."
)
@click.option(
    "--downloads-3y",
    type=int,
    default=10,
    show_default=True,
    help="Download events per dataset backdated to the 3-year window.",
)
@click.option(
    "--downloads-90d",
    type=int,
    default=5,
    show_default=True,
    help="Download events per dataset backdated to the last 90 days.",
)
@click.option(
    "--dataset-ref",
    multiple=True,
    help="Restrict to specific dataset name/id. Can be repeated. Omit to target all supported datasets.",
)
@click.option("--limit", type=int, default=None, help="Process at most this many datasets.")
@click.option("--offset", type=int, default=None, help="Skip this many datasets before starting.")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be sent without emitting any events.")
def generate_bulk_traffic(
    visits_3y: int,
    visits_90d: int,
    downloads_3y: int,
    downloads_90d: int,
    dataset_ref: tuple[str],
    limit: int | None,
    offset: int | None,
    dry_run: bool,
):
    """Generate fake Matomo traffic for every active dataset of every type.

    Iterates all datasets of types: data, information, access-requests,
    pia-summaries.  Events are spread across two windows:

      3-year window  — random timestamps older than 90 days
      90-day window  — random timestamps within the last 90 days

    Each pageview uses a unique visitor ID so Matomo counts it as a
    distinct visit.  Datasets without resources get their download counts
    set to 0 automatically.
    """
    summary = matomo_traffic.generate_bulk_traffic(
        visits_3y=visits_3y,
        visits_90d=visits_90d,
        downloads_3y=downloads_3y,
        downloads_90d=downloads_90d,
        dataset_refs=list(dataset_ref) if dataset_ref else None,
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
