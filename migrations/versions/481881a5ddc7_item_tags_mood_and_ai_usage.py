"""item tags (several seasons, styles, moods), mood options, AI usage

Revision ID: 481881a5ddc7
Revises: dd7f3e926763
Create Date: 2026-11-07 19:40:00

Item.season and Item.style held one word each. Now an item can have
several, so they move to a new table, item_tag, one row per choice:
- season "all" becomes no season rows (no rows = all seasons),
- style "home" becomes the new mood "home" (and the style is hidden),
- every other season and style is copied as it is.
Then the two old columns are dropped.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '481881a5ddc7'
down_revision = 'dd7f3e926763'
branch_labels = None
depends_on = None

MOODS = ["home", "comfortable", "classy", "elegant"]
NEW_STYLES = ["minimalist", "vintage"]


def upgrade():
    op.create_table('item_tag',
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('value', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['item.id'], ),
    sa.PrimaryKeyConstraint('item_id', 'kind', 'value')
    )
    with op.batch_alter_table('item_tag', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_item_tag_value'), ['value'], unique=False)

    op.create_table('ai_usage',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'day')
    )

    # Copy the old one-word columns into item_tag (plain SQL, runs inside
    # the database, so it's fast even with many items).
    op.execute("INSERT INTO item_tag (item_id, kind, value) "
               "SELECT id, 'season', season FROM item WHERE season IS NOT NULL AND season != 'all'")
    op.execute("INSERT INTO item_tag (item_id, kind, value) "
               "SELECT id, 'style', style FROM item WHERE style IS NOT NULL AND style != '' AND style != 'home'")
    op.execute("INSERT INTO item_tag (item_id, kind, value) "
               "SELECT id, 'mood', 'home' FROM item WHERE style = 'home'")

    # The mood list, for the admin page and the form. Skipped on a fresh
    # database: seed.py fills it there.
    option = sa.table('option', sa.column('kind', sa.String), sa.column('value', sa.String),
                      sa.column('position', sa.Integer), sa.column('hidden', sa.Boolean))
    connection = op.get_bind()
    has_options = connection.execute(sa.text("SELECT COUNT(*) FROM option")).scalar()
    if has_options:
        existing = {row[0] for row in connection.execute(
            sa.text("SELECT value FROM option WHERE kind = 'mood'"))}
        op.bulk_insert(option, [{"kind": "mood", "value": value, "position": position, "hidden": False}
                                for position, value in enumerate(MOODS) if value not in existing])
        op.execute("UPDATE option SET hidden = 1 WHERE kind = 'style' AND value = 'home'")
        # Two new styles (from the screenshot idea), at the end of the list.
        styles = {row[0] for row in connection.execute(
            sa.text("SELECT value FROM option WHERE kind = 'style'"))}
        op.bulk_insert(option, [{"kind": "style", "value": value, "position": 20 + n, "hidden": False}
                                for n, value in enumerate(NEW_STYLES) if value not in styles])

    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.drop_column('style')
        batch_op.drop_column('season')


def downgrade():
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('season', sa.VARCHAR(length=20), nullable=False, server_default='all'))
        batch_op.add_column(sa.Column('style', sa.VARCHAR(length=30), nullable=True))
    # Only one season and one style fit in the old columns: keep the first.
    op.execute("UPDATE item SET season = COALESCE((SELECT MIN(value) FROM item_tag "
               "WHERE item_tag.item_id = item.id AND kind = 'season'), 'all')")
    op.execute("UPDATE item SET style = (SELECT MIN(value) FROM item_tag "
               "WHERE item_tag.item_id = item.id AND kind = 'style')")
    op.execute("DELETE FROM option WHERE kind = 'mood'")
    op.execute("UPDATE option SET hidden = 0 WHERE kind = 'style' AND value = 'home'")
    op.execute("DELETE FROM option WHERE kind = 'style' AND value IN ('minimalist', 'vintage')")
    op.drop_table('ai_usage')
    with op.batch_alter_table('item_tag', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_item_tag_value'))
    op.drop_table('item_tag')
