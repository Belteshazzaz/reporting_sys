"""add report attachments unified table

Revision ID: e2d643ee2ada
Revises: f0947fec4661
Create Date: 2026-03-05 16:36:21.593078

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2d643ee2ada'
down_revision = 'f0947fec4661'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite does not support named FK constraints in ALTER TABLE.
    # We use batch_alter_table with recreate='always' so Alembic
    # rebuilds the table from scratch — the safe way on SQLite.
    with op.batch_alter_table('report_attachments', schema=None, recreate='always') as batch_op:
        batch_op.add_column(sa.Column('complaint_id', sa.Integer(), nullable=True))
        batch_op.alter_column('report_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('file_type',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=50),
               existing_nullable=False)
        batch_op.alter_column('uploaded_by',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_foreign_key('fk_attachment_uploaded_by', 'users', ['uploaded_by'], ['id'])
        batch_op.create_foreign_key('fk_attachment_complaint_id', 'consumer_complaints', ['complaint_id'], ['id'])


def downgrade():
    with op.batch_alter_table('report_attachments', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('complaint_id')
        batch_op.alter_column('report_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('file_type',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
        batch_op.alter_column('uploaded_by',
               existing_type=sa.INTEGER(),
               nullable=False)
