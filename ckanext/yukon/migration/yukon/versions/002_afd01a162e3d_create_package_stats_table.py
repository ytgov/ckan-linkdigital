"""Create package_stats table.

Revision ID: afd01a162e3d
Revises: cc1a832108c5
Create Date: 2026-07-08 14:16:06.787344

"""

import sqlalchemy as sa
from alembic import op

from ckan import model

# revision identifiers, used by Alembic.
revision = "afd01a162e3d"
down_revision = "cc1a832108c5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "yukon_package_stats",
        sa.Column("id", sa.UnicodeText(), nullable=False),
        sa.Column("total_visits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_downloads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_quarter_visits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_quarter_downloads", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["id"], ["package.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_table("yukon_something")
    if hasattr(model, "PackageExtra"):
        op.get_bind().execute(
            sa.delete(model.PackageExtra).where(
                model.PackageExtra.key.in_(["visits", "download_90_days", "downloads", "visit_90_days"])
            )
        )


def downgrade():
    op.create_table(
        "yukon_something",
    )
    op.drop_table("yukon_package_stats")
