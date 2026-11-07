"""undertone and body shape on user, for outfit suggestions

Revision ID: 7c3e5a9d1f20
Revises: 481881a5ddc7
Create Date: 2026-11-07 19:40:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c3e5a9d1f20'
down_revision = '481881a5ddc7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('undertone', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('body_shape', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('body_shape')
        batch_op.drop_column('undertone')
