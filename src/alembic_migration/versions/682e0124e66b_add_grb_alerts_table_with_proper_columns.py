"""add_grb_alerts_table_with_proper_columns

Revision ID: 682e0124e66b
Revises: a812e32a489d
Create Date: 2025-12-12 09:55:49.857237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '682e0124e66b'
down_revision: Union[str, Sequence[str], None] = 'a812e32a489d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'grb_alerts',
        sa.Column('id_grb', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('triggerId', sa.String(), nullable=False),
        sa.Column('mission', sa.String(), nullable=True),
        sa.Column('packet_type', sa.Integer(), nullable=True),
        sa.Column('ra', sa.Float(), nullable=True),
        sa.Column('dec', sa.Float(), nullable=True),
        sa.Column('error_deg', sa.Float(), nullable=True),
        sa.Column('trigger_time', sa.DateTime(), nullable=True),
        sa.Column('reception_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('thread_ts', sa.String(), nullable=True),
        sa.Column('xml_payload', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id_grb')
    )
    op.create_index('ix_grb_alerts_triggerId', 'grb_alerts', ['triggerId'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_grb_alerts_triggerId', table_name='grb_alerts')
    op.drop_table('grb_alerts')
