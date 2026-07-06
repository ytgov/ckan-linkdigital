"""Create something table.

Revision ID: cc1a832108c5
Revises:
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "cc1a832108c5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("yukon_something")


def downgrade():
    op.drop_table("yukon_something")
