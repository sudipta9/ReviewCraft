"""Initial database schema

Revision ID: db2c4dd1a657
Revises: 
Create Date: 2025-07-27 10:51:38.821880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db2c4dd1a657'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tasks',
    sa.Column('celery_task_id', sa.String(length=255), nullable=True),
    sa.Column('task_type', sa.String(length=50), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('repo_url', sa.String(length=500), nullable=False),
    sa.Column('repo_owner', sa.String(length=100), nullable=False),
    sa.Column('repo_name', sa.String(length=100), nullable=False),
    sa.Column('pr_number', sa.Integer(), nullable=False),
    sa.Column('pr_title', sa.String(length=500), nullable=True),
    sa.Column('pr_author', sa.String(length=100), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('error_details', sa.JSON(), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=False),
    sa.Column('max_retries', sa.Integer(), nullable=False),
    sa.Column('config', sa.JSON(), nullable=True),
    sa.Column('github_token_used', sa.Boolean(), nullable=False),
    sa.Column('rate_limit_remaining', sa.Integer(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_celery_task_id'), 'tasks', ['celery_task_id'], unique=True)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)
    op.create_table('pr_analyses',
    sa.Column('task_id', sa.String(length=36), nullable=False),
    sa.Column('pr_url', sa.String(length=500), nullable=False),
    sa.Column('base_branch', sa.String(length=200), nullable=False),
    sa.Column('head_branch', sa.String(length=200), nullable=False),
    sa.Column('base_sha', sa.String(length=40), nullable=False),
    sa.Column('head_sha', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('analysis_started_at', sa.DateTime(), nullable=True),
    sa.Column('analysis_completed_at', sa.DateTime(), nullable=True),
    sa.Column('total_files_analyzed', sa.Integer(), nullable=False),
    sa.Column('total_lines_analyzed', sa.Integer(), nullable=False),
    sa.Column('total_issues_found', sa.Integer(), nullable=False),
    sa.Column('critical_issues', sa.Integer(), nullable=False),
    sa.Column('high_issues', sa.Integer(), nullable=False),
    sa.Column('medium_issues', sa.Integer(), nullable=False),
    sa.Column('low_issues', sa.Integer(), nullable=False),
    sa.Column('info_issues', sa.Integer(), nullable=False),
    sa.Column('quality_score', sa.Float(), nullable=True),
    sa.Column('maintainability_score', sa.Float(), nullable=True),
    sa.Column('complexity_score', sa.Float(), nullable=True),
    sa.Column('ai_model_used', sa.String(length=100), nullable=True),
    sa.Column('ai_tokens_consumed', sa.Integer(), nullable=True),
    sa.Column('ai_analysis_duration', sa.Float(), nullable=True),
    sa.Column('analysis_config', sa.JSON(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('recommendations', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pr_analyses_task_id'), 'pr_analyses', ['task_id'], unique=False)
    op.create_table('file_analyses',
    sa.Column('pr_analysis_id', sa.String(length=36), nullable=False),
    sa.Column('file_path', sa.String(length=1000), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('file_extension', sa.String(length=10), nullable=True),
    sa.Column('file_type', sa.String(length=50), nullable=True),
    sa.Column('lines_total', sa.Integer(), nullable=True),
    sa.Column('lines_analyzed', sa.Integer(), nullable=True),
    sa.Column('lines_added', sa.Integer(), nullable=True),
    sa.Column('lines_removed', sa.Integer(), nullable=True),
    sa.Column('analysis_status', sa.String(length=20), nullable=False),
    sa.Column('complexity_score', sa.Float(), nullable=True),
    sa.Column('maintainability_index', sa.Float(), nullable=True),
    sa.Column('test_coverage', sa.Float(), nullable=True),
    sa.Column('issues_count', sa.Integer(), nullable=False),
    sa.Column('critical_issues_count', sa.Integer(), nullable=False),
    sa.Column('ai_summary', sa.Text(), nullable=True),
    sa.Column('ai_recommendations', sa.JSON(), nullable=True),
    sa.Column('diff_content', sa.Text(), nullable=True),
    sa.Column('analysis_tools_used', sa.JSON(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['pr_analysis_id'], ['pr_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_file_analyses_pr_analysis_id'), 'file_analyses', ['pr_analysis_id'], unique=False)
    op.create_table('issues',
    sa.Column('pr_analysis_id', sa.String(length=36), nullable=False),
    sa.Column('file_analysis_id', sa.String(length=36), nullable=True),
    sa.Column('issue_type', sa.String(length=30), nullable=False),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('file_path', sa.String(length=1000), nullable=True),
    sa.Column('line_number', sa.Integer(), nullable=True),
    sa.Column('column_number', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('code_snippet', sa.Text(), nullable=True),
    sa.Column('suggestion', sa.Text(), nullable=True),
    sa.Column('suggested_code', sa.Text(), nullable=True),
    sa.Column('rule_id', sa.String(length=100), nullable=True),
    sa.Column('tool_name', sa.String(length=50), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=True),
    sa.Column('references', sa.JSON(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['file_analysis_id'], ['file_analyses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['pr_analysis_id'], ['pr_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_issues_file_analysis_id'), 'issues', ['file_analysis_id'], unique=False)
    op.create_index(op.f('ix_issues_issue_type'), 'issues', ['issue_type'], unique=False)
    op.create_index(op.f('ix_issues_pr_analysis_id'), 'issues', ['pr_analysis_id'], unique=False)
    op.create_index(op.f('ix_issues_severity'), 'issues', ['severity'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_issues_severity'), table_name='issues')
    op.drop_index(op.f('ix_issues_pr_analysis_id'), table_name='issues')
    op.drop_index(op.f('ix_issues_issue_type'), table_name='issues')
    op.drop_index(op.f('ix_issues_file_analysis_id'), table_name='issues')
    op.drop_table('issues')
    op.drop_index(op.f('ix_file_analyses_pr_analysis_id'), table_name='file_analyses')
    op.drop_table('file_analyses')
    op.drop_index(op.f('ix_pr_analyses_task_id'), table_name='pr_analyses')
    op.drop_table('pr_analyses')
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_celery_task_id'), table_name='tasks')
    op.drop_table('tasks')
    # ### end Alembic commands ###
