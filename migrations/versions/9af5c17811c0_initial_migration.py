"""Initial migration

Revision ID: 9af5c17811c0
Revises: f3fe56271a52
Create Date: 2025-04-01 11:09:58.697001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9af5c17811c0'
down_revision = 'f3fe56271a52'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=500),
               type_=sa.String(length=400),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.String(length=400),
               type_=sa.VARCHAR(length=500),
               existing_nullable=True)

    # ### end Alembic commands ###
