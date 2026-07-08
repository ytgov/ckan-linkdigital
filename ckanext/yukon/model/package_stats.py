from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm.relationships import RelationshipProperty

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.lib.dictization import table_dictize

foreign: Any


class PackageStats(tk.BaseModel):  # pyright: ignore[reportUntypedBaseClass]
    """Model with Matomo analytics details.

    Keyword Args:
        id (str): ID of the tracked dataset
        total_visits(int): numbrer of package visits in total
        total_downloads(int): number of package(resource) downloads in total
        last_quarter_visits(int): number of package visits in the last quarter
        last_quarter_downloads(int): number of package(resource) downloads in the last quarter

    Example:
        ```python
        file = PackageStats(id=pkg.id, total_visits=12)
        ```
    """

    __table__ = sa.Table(
        "yukon_package_stats",
        tk.BaseModel.metadata,
        sa.Column("id", sa.UnicodeText, sa.ForeignKey(model.Package.id), primary_key=True),
        sa.Column("total_visits", sa.Integer, nullable=False, default=0),
        sa.Column("total_downloads", sa.Integer, nullable=False, default=0),
        sa.Column("last_quarter_visits", sa.Integer, nullable=False, default=0),
        sa.Column("last_quarter_downloads", sa.Integer, nullable=False, default=0),
    )

    id: Mapped[str]
    total_visits: Mapped[int]
    total_downloads: Mapped[int]
    last_quarter_visits: Mapped[int]
    last_quarter_downloads: Mapped[int]

    package: RelationshipProperty[model.Package] = relationship(
        model.Package,
        uselist=False,
        lazy="joined",
    )

    def dictize(self) -> dict[str, Any]:
        return table_dictize(self, {})
