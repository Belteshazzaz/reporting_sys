"""add office_type and department to users

Revision ID: c3f1a2b4d5e6
Revises: 85975d7b3ae5
Create Date: 2026-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'c3f1a2b4d5e6'
down_revision = '85975d7b3ae5'
branch_labels = None
depends_on = None


def _col_exists(table, col):
    bind = op.get_bind()
    cols = [c['name'] for c in inspect(bind).get_columns(table)]
    return col in cols


def upgrade():
    with op.batch_alter_table('users', schema=None, recreate='always') as batch_op:
        if not _col_exists('users', 'office_type'):
            batch_op.add_column(sa.Column(
                'office_type', sa.String(length=20),
                nullable=False, server_default='Zonal/State'
            ))
        if not _col_exists('users', 'department'):
            batch_op.add_column(sa.Column(
                'department', sa.String(length=100), nullable=True
            ))


def downgrade():
    with op.batch_alter_table('users', schema=None, recreate='always') as batch_op:
        if _col_exists('users', 'department'):
            batch_op.drop_column('department')
        if _col_exists('users', 'office_type'):
            batch_op.drop_column('office_type')
