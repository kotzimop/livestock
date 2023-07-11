"""empty message

Revision ID: 4cde42186463
Revises: e33f42227ced
Create Date: 2023-01-17 19:54:45.195337

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4cde42186463'
down_revision = 'e33f42227ced'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('milkings', sa.Column('total_milk_up_to_today', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('milkings', 'total_milk_up_to_today')
    # ### end Alembic commands ###