"""feedback: ideas users send for the app

Revision ID: b1f4c2e8a7d3
Revises: 7c3e5a9d1f20
Create Date: 2026-11-07 20:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1f4c2e8a7d3'
down_revision = '7c3e5a9d1f20'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_feedback_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_feedback_user_id'))
    op.drop_table('feedback')
