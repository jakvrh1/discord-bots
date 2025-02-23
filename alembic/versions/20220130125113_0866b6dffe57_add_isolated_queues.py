"""Add isolated queues

Revision ID: 0866b6dffe57
Revises: 509440a9c704
Create Date: 2022-01-30 12:51:13.174631

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0866b6dffe57"
down_revision = "509440a9c704"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("queue", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_isolated",
                sa.Boolean(),
                server_default=sa.text("False"),
                nullable=False,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_queue_is_isolated"), ["is_isolated"], unique=False
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("queue", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_queue_is_isolated"))
        batch_op.drop_column("is_isolated")

    # ### end Alembic commands ###
