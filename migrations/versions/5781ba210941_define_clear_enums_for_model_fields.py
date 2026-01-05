"""define clear enums for model fields

Revision ID: 5781ba210941
Revises: 5dc15cca803e
Create Date: 2026-01-04 23:21:25.957776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5781ba210941'
down_revision: Union[str, Sequence[str], None] = '5dc15cca803e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---------- ENUM DEFINITIONS ----------
    itemtype = sa.Enum('lost', 'found', name='itemtype')
    visibilitytype = sa.Enum('public', 'boys', 'girls', name='visibilitytype')
    hiddenreasontype = sa.Enum(
        'auto_report_threshold', 'admin_moderation',
        name='hiddenreasontype'
    )
    notificationtype = sa.Enum(
        'claim_created', 'claim_approved', 'claim_rejected',
        'system_notice', 'warning_issued',
        name='notificationtype'
    )
    reportreason = sa.Enum(
        'spam', 'inappropriate', 'harassment', 'fake', 'other',
        name='reportreason'
    )
    reportstatus = sa.Enum('pending', 'reviewed', name='reportstatus')
    statustype = sa.Enum('pending', 'approved', 'rejected', name='statustype')
    hosteltype = sa.Enum('boys', 'girls', name='hosteltype')
    roletype = sa.Enum('user', 'admin', name='roletype')

    # ---------- CREATE ENUMS ----------
    for enum in [
        itemtype, visibilitytype, hiddenreasontype, notificationtype,
        reportreason, reportstatus, statustype, hosteltype, roletype
    ]:
        enum.create(bind, checkfirst=True)

    # ---------- ALTER COLUMNS ----------
    op.alter_column(
        'items',
        'type',
        existing_type=sa.VARCHAR(),
        type_=itemtype,
        existing_nullable=False,
        postgresql_using="type::itemtype",
    )

    op.alter_column(
        'items',
        'visibility',
        existing_type=sa.VARCHAR(),
        type_=visibilitytype,
        existing_nullable=False,
        postgresql_using="visibility::visibilitytype",
    )

    op.alter_column(
        'items',
        'hidden_reason',
        existing_type=sa.VARCHAR(),
        type_=hiddenreasontype,
        existing_nullable=True,
        postgresql_using="hidden_reason::hiddenreasontype",
    )

    op.create_index(op.f('ix_items_type'), 'items', ['type'])
    op.create_index(op.f('ix_items_visibility'), 'items', ['visibility'])

    op.alter_column(
        'notifications', 
        'type',
        existing_type=sa.VARCHAR(),
        type_=notificationtype,
        existing_nullable=False,
        postgresql_using="type::notificationtype",
    )

    op.alter_column(
        'reports',
        'reason',
        existing_type=sa.VARCHAR(),
        type_=reportreason,
        existing_nullable=False,
        postgresql_using="reason::reportreason",
    )

    op.alter_column(
        'reports',
        'status',
        existing_type=sa.VARCHAR(),
        type_=reportstatus,
        existing_nullable=False,
        postgresql_using="status::reportstatus",
    )

    op.create_index(op.f('ix_reports_reason'), 'reports', ['reason'])

    op.alter_column(
        'resolutions',
        'status',
        existing_type=sa.VARCHAR(),
        type_=statustype,
        existing_nullable=False,
        postgresql_using="status::statustype",
    )

    op.alter_column(
        'users',
        'role',
        existing_type=sa.VARCHAR(),
        type_=roletype,
        existing_nullable=False,
        postgresql_using="role::roletype",
    )

    op.alter_column(
        'users',
        'hostel',
        existing_type=sa.VARCHAR(),
        type_=hosteltype,
        existing_nullable=True,
        postgresql_using="hostel::hosteltype",
    )


def downgrade() -> None:
    bind = op.get_bind()

    # ---------- ALTER COLUMNS BACK ----------
    op.alter_column('users', 'role',
        existing_type=sa.Enum(name='roletype'),
        type_=sa.VARCHAR(),
        existing_nullable=False
    )

    op.alter_column('users', 'hostel',
        existing_type=sa.Enum(name='hosteltype'),
        type_=sa.VARCHAR(),
        existing_nullable=True
    )

    op.alter_column('resolutions', 'status',
        existing_type=sa.Enum(name='statustype'),
        type_=sa.VARCHAR(),
        existing_nullable=False
    )

    op.drop_index(op.f('ix_reports_reason'), table_name='reports')

    op.alter_column('reports', 'status',
        existing_type=sa.Enum(name='reportstatus'),
        type_=sa.VARCHAR(),
        existing_nullable=False
    )

    op.alter_column('reports', 'reason',
        existing_type=sa.Enum(name='reportreason'),
        type_=sa.VARCHAR(),
        existing_nullable=False
    )

    op.alter_column('notifications', 'type',
        existing_type=sa.Enum(name='notificationtype'),
        type_=sa.VARCHAR(),
        existing_nullable=False
    )

    op.drop_index(op.f('ix_items_visibility'), table_name='items')
    op.drop_index(op.f('ix_items_type'), table_name='items')

    op.alter_column('items', 'hidden_reason',
        existing_type=sa.Enum(name='hiddenreasontype'),
        type_=sa.VARCHAR(),
        existing_nullable=True
    )

    op.alter_column('items', 'visibility',
        existing_type=sa.Enum(name='visibilitytype'),
        type_=sa.VARCHAR(),
        existing_nullable=False
    )

    op.alter_column('items', 'type',
        existing_type=sa.Enum(name='itemtype'),
        type_=sa.VARCHAR(),
        existing_nullable=False
    )

    # ---------- DROP ENUMS ----------
    for enum_name in [
        'itemtype', 'visibilitytype', 'hiddenreasontype',
        'notificationtype', 'reportreason', 'reportstatus',
        'statustype', 'hosteltype', 'roletype'
    ]:
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
