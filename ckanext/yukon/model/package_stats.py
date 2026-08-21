from __future__ import annotations

from typing import Annotated, Any, ClassVar

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from ckan import model
from ckan.lib.dictization import table_dictize

text = Annotated[str, mapped_column(sa.TEXT)]


@model.registry.mapped_as_dataclass
class PackageStats:
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

    __table__: ClassVar[sa.Table]

    __tablename__: ClassVar[str] = "yukon_package_stats"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        sa.ForeignKeyConstraint(
            ["id"],
            ["package.id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[text] = mapped_column(primary_key=True)
    total_visits: Mapped[int] = mapped_column(default=0)
    total_downloads: Mapped[int] = mapped_column(default=0)
    last_quarter_visits: Mapped[int] = mapped_column(default=0)
    last_quarter_downloads: Mapped[int] = mapped_column(default=0)

    package: Mapped[model.Package] = relationship(
        model.Package,
        lazy="joined",
        backref=backref("yukon_stats", uselist=False, passive_deletes=True),
        init=False,
        compare=False,
    )

    def dictize(self) -> dict[str, Any]:
        return table_dictize(self, {})
