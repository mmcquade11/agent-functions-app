"""add prompt and agent tables

Revision ID: 20240430_add_prompt_and_agent
Revises: 
Create Date: 2025-04-30 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

# revision identifiers, used by Alembic.
revision = '20240430_add_prompt_and_agent'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'prompts',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('original_prompt', sa.Text(), nullable=False),
        sa.Column('optimized_prompt', sa.Text(), nullable=True),
        sa.Column('needs_reasoning', sa.String(), nullable=False, default="false"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'agents',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', pg.UUID(as_uuid=True), sa.ForeignKey('prompts.id', ondelete='CASCADE')),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), default="draft"),
        sa.Column('agent_code', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

def downgrade():
    op.drop_table('agents')
    op.drop_table('prompts')
