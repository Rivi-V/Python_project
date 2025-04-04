"""Initial migration

Revision ID: f3fe56271a52
Revises: c851591e2fae
Create Date: 2025-04-01 11:08:28.699131

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3fe56271a52'
down_revision = 'c851591e2fae'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=400),
               type_=sa.String(length=500),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=400),
               existing_nullable=True)

    # ### end Alembic commands ###
