"""add department to custom_templates

Revision ID: d4e5f6a7b8c9
Revises: c3f1a2b4d5e6
Create Date: 2026-03-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'd4e5f6a7b8c9'
down_revision = 'c3f1a2b4d5e6'
branch_labels = None
depends_on = None


def _col_exists(table, col):
    bind = op.get_bind()
    cols = [c['name'] for c in inspect(bind).get_columns(table)]
    return col in cols


def upgrade():
    with op.batch_alter_table('custom_templates', schema=None, recreate='always') as batch_op:
        if not _col_exists('custom_templates', 'department'):
            batch_op.add_column(sa.Column('department', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('custom_templates', schema=None, recreate='always') as batch_op:
        if _col_exists('custom_templates', 'department'):
            batch_op.drop_column('department')
