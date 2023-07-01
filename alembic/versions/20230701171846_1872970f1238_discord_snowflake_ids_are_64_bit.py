"""discord snowflake ids are 64 bit

Revision ID: 1872970f1238
Revises: 9e790b5beb2d
Create Date: 2023-07-01 17:18:46.234034

"""
import logging


from alembic import op


# revision identifiers, used by Alembic.
revision = "1872970f1238"
down_revision = "9e790b5beb2d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE admin_role ALTER COLUMN role_id TYPE bigint USING role_id::bigint')
    op.execute('ALTER TABLE in_progress_game_player ALTER COLUMN player_id TYPE bigint USING player_id::bigint')
    op.execute('ALTER TABLE in_progress_game_channel ALTER COLUMN channel_id TYPE bigint USING channel_id::bigint')
    op.execute('ALTER TABLE map_vote ALTER COLUMN player_id TYPE bigint USING player_id::bigint')
    op.execute('ALTER TABLE skip_map_vote ALTER COLUMN player_id TYPE bigint USING player_id::bigint')
    op.execute('ALTER TABLE player ALTER COLUMN id TYPE bigint USING id::bigint')
    op.execute('ALTER TABLE player_region_trueskill ALTER COLUMN player_id TYPE bigint USING player_id::bigint')
    op.execute('ALTER TABLE queue_notification ALTER COLUMN player_id TYPE bigint USING player_id::bigint')
    op.execute('ALTER TABLE queue_player ALTER COLUMN player_id TYPE bigint USING player_id::bigint')
    op.execute('ALTER TABLE queue_role ALTER COLUMN role_id TYPE bigint USING role_id::bigint')
    op.execute('ALTER TABLE queue_waitlist_player ALTER COLUMN player_id TYPE bigint USING player_id::bigint')
    op.execute('ALTER TABLE vote_passed_waitlist_player ALTER COLUMN player_id TYPE bigint USING player_id::bigint')


def downgrade():
    logging.warning("Downgrading could destroy data.")
    logging.warning("When an ID that requires BIGINT is stored in the DB the migration will fail.")
    logging.warning("It may be restricted to admin_role and queue_role in which case you may remove the roles, "
                    "but the feature will not work after downgrading.")

    op.execute('ALTER TABLE admin_role ALTER COLUMN role_id TYPE integer USING role_id::integer')
    op.execute('ALTER TABLE in_progress_game_player ALTER COLUMN player_id TYPE integer USING player_id::integer')
    op.execute('ALTER TABLE in_progress_game_channel ALTER COLUMN channel_id TYPE integer USING channel_id::integer')
    op.execute('ALTER TABLE map_vote ALTER COLUMN player_id TYPE integer USING player_id::integer')
    op.execute('ALTER TABLE skip_map_vote ALTER COLUMN player_id TYPE integer USING player_id::integer')
    op.execute('ALTER TABLE player ALTER COLUMN id TYPE integer USING id::integer')
    op.execute('ALTER TABLE player_region_trueskill ALTER COLUMN player_id TYPE integer USING player_id::integer')
    op.execute('ALTER TABLE queue_notification ALTER COLUMN player_id TYPE integer USING player_id::integer')
    op.execute('ALTER TABLE queue_player ALTER COLUMN player_id TYPE integer USING player_id::integer')
    op.execute('ALTER TABLE queue_role ALTER COLUMN role_id TYPE integer USING role_id::integer')
    op.execute('ALTER TABLE queue_waitlist_player ALTER COLUMN player_id TYPE integer USING player_id::integer')
    op.execute('ALTER TABLE vote_passed_waitlist_player ALTER COLUMN player_id TYPE integer USING player_id::integer')
