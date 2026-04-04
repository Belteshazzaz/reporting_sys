"""add custom template builder

Revision ID: 85975d7b3ae5
Revises: e2d643ee2ada
Create Date: 2026-03-10 15:12:12.702146

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '85975d7b3ae5'
down_revision = 'e2d643ee2ada'
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def upgrade():
    if not _table_exists('custom_templates'):
        op.create_table('custom_templates',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('code', sa.String(length=20), nullable=False),
            sa.Column('slug', sa.String(length=100), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('slug')
        )

    if not _table_exists('custom_template_fields'):
        op.create_table('custom_template_fields',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('template_id', sa.Integer(), nullable=False),
            sa.Column('field_key', sa.String(length=100), nullable=False),
            sa.Column('label', sa.String(length=255), nullable=False),
            sa.Column('field_type', sa.String(length=50), nullable=False),
            sa.Column('options', sa.Text(), nullable=True),
            sa.Column('is_required', sa.Boolean(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['template_id'], ['custom_templates.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    with op.batch_alter_table('report_attachments', schema=None, recreate='always') as batch_op:
        batch_op.create_foreign_key('fk_attachment_uploaded_by', 'users', ['uploaded_by'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_attachment_complaint_id', 'consumer_complaints', ['complaint_id'], ['id'], ondelete='CASCADE')


def downgrade():
    with op.batch_alter_table('report_attachments', schema=None, recreate='always') as batch_op:
        batch_op.drop_constraint('fk_attachment_uploaded_by', type_='foreignkey')
        batch_op.drop_constraint('fk_attachment_complaint_id', type_='foreignkey')

    if _table_exists('custom_template_fields'):
        op.drop_table('custom_template_fields')
    if _table_exists('custom_templates'):
        op.drop_table('custom_templates')
