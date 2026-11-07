"""suggestion votes: "Wear it" / "Not for me", so suggestions learn

Revision ID: c4d8e1f2a9b6
Revises: b1f4c2e8a7d3
Create Date: 2026-11-07 21:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d8e1f2a9b6'
down_revision = 'b1f4c2e8a7d3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'suggestion_vote',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('item_ids', sa.String(length=200), nullable=False),
        sa.Column('liked', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('suggestion_vote', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_suggestion_vote_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('suggestion_vote', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_suggestion_vote_user_id'))
    op.drop_table('suggestion_vote')
