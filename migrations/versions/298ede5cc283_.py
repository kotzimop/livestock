"""empty message

Revision ID: 298ede5cc283
Revises: c31a1db2ac29
Create Date: 2023-01-09 09:00:03.593911

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '298ede5cc283'
down_revision = 'c31a1db2ac29'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('animal_alerts', sa.Column('date_recorded', sa.Date(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('animal_alerts', 'date_recorded')
    # ### end Alembic commands ###