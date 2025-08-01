"""Add unique constraint on message_ts and owncloud_url attribute

Revision ID: a812e32a489d
Revises: 79b89c014192
Create Date: 2025-07-21 11:36:08.458308

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a812e32a489d"
down_revision: str | Sequence[str] | None = "79b89c014192"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("gw_alerts", sa.Column("owncloud_url", sa.String(), nullable=True))
    op.create_unique_constraint(None, "gw_alerts", ["message_ts"])
    op.create_unique_constraint(None, "gw_alerts", ["owncloud_url"])
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "gw_alerts", type_="unique")
    op.drop_constraint(None, "gw_alerts", type_="unique")
    op.drop_column("gw_alerts", "owncloud_url")
    # ### end Alembic commands ###
