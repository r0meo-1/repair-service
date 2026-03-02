"""Initial migration

Revision ID: 0001
Revises: 
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_table(
        'requests',
        sa.Column('r_id', sa.Integer(), nullable=False),
        sa.Column('clientName', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('problemText', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('new', 'assigned', 'in_progress', 'done', name='statusenum'), nullable=True),
        sa.Column('assignedTo', sa.Integer(), nullable=True),
        sa.Column('createdAt', sa.DateTime(), nullable=True),
        sa.Column('updatedAt', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assignedTo'], ['users.id']),
        sa.PrimaryKeyConstraint('r_id')
    )


def downgrade() -> None:
    op.drop_table('requests')
    op.drop_table('users')
