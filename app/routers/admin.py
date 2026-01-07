from typing import Literal, Optional, List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, and_, update
from sqlalchemy.orm import aliased
import uuid

from app.db.db import get_session
from app.models.user import User
from app.models.item import Item
from app.models.resolution import Resolution
from app.models.report import Report
from app.utils.auth_helper import get_db_user, get_require_admin
from app.models.notification import Notification
from app.schemas.admin_schemas import *

router = APIRouter()

@router.get("/stats", response_model=OverviewStats)
def get_overview_stats(
    session: Session = Depends(get_session),
    admin: User = Depends(get_require_admin)
):
    """Get overview statistics for the admin dashboard"""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    prev_month_end = month_start
    prev_month_start = (
        month_start - timedelta(days=1)
    ).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Items
    total_items, items_this_month, items_last_month = session.exec(
        select(
            func.count(Item.id),
            func.count().filter(Item.created_at >= month_start),
            func.count().filter(
                and_(
                    Item.created_at >= prev_month_start,
                    Item.created_at < prev_month_end,
                )
            ),
        )
    ).one()

    # Claims
    ( 
        claims_approved_this_month,
        claims_approved_last_month,
        claims_rejected_this_month,
        claims_rejected_last_month,
        claims_pending 
    ) = session.exec(
        select(
            func.count().filter(
                and_(
                    Resolution.status == "approved",
                    Resolution.decided_at >= month_start,
                )
            ),
            func.count().filter(
                and_(
                    Resolution.status == "approved",
                    Resolution.decided_at >= prev_month_start,
                    Resolution.decided_at < prev_month_end,
                )
            ),
            func.count().filter(
                and_(
                    Resolution.status == "rejected",
                    Resolution.decided_at >= month_start,
                )
            ),
            func.count().filter(
                and_(
                    Resolution.status == "rejected",
                    Resolution.decided_at >= prev_month_start,
                    Resolution.decided_at < prev_month_end,
                )
            ),
            func.count().filter(Resolution.status == "pending"),
        )
    ).one()

    # Reports
    (
        active_reports,
        reports_this_month,
        reports_last_month,
    ) = session.exec(
        select(
            func.count().filter(Report.status == "pending"),
            func.count().filter(Report.created_at >= month_start),
            func.count().filter(
                and_(
                    Report.created_at >= prev_month_start,
                    Report.created_at < prev_month_end,
                )
            ),
        )
    ).one()

    (
        total_users,
        users_this_month,
        users_last_month,
    ) = session.exec(
        select(
            func.count(User.id),
            func.count().filter(User.created_at >= month_start),
            func.count().filter(
                and_(
                    User.created_at >= prev_month_start,
                    User.created_at < prev_month_end,
                )
            ),
        )
    ).one()

    return OverviewStats(
        total_items=total_items,
        items_this_month=items_this_month,
        items_last_month=items_last_month,
        
        claims_approved_this_month=claims_approved_this_month,
        claims_approved_last_month=claims_approved_last_month,
        claims_rejected_this_month=claims_rejected_this_month,
        claims_rejected_last_month=claims_rejected_last_month,
        claims_pending=claims_pending,

        active_reports=active_reports,
        reports_this_month=reports_this_month,
        reports_last_month=reports_last_month,

        total_users=total_users,
        users_this_month=users_this_month,
        users_last_month=users_last_month,
    )


@router.get("/activity", response_model=List[ActivityItem])
def get_recent_activity(
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_require_admin),
):
    """Get recent admin activity feed"""

    activities: list[ActivityItem] = []

    claim_limit = max(5, limit // 2)
    report_limit = max(5, limit // 2)
    system_limit = min(5, limit)

    claim_descriptions = {
        "approved": "Approved",
        "rejected": "Rejected",
        "pending": "Pending Review",
    }

    claims = session.exec(
        select(Resolution, Item, User)
        .join(Item, Resolution.found_item_id == Item.id)
        .join(User, Resolution.claimant_id == User.id)
        .order_by(Resolution.created_at.desc())
        .limit(claim_limit)
    ).all()

    for res, item, user in claims:
        activities.append(ActivityItem(
            id=str(res.id),
            type=f"claim_{res.status}",
            description=f"{user.name} claimed '{item.title}' - {claim_descriptions[res.status]}",
            timestamp=res.decided_at or res.created_at,
        ))

    # Reports
    reports = session.exec(
        select(Report, Item, User)
        .join(Item, Report.item_id == Item.id)
        .join(User, Report.user_id == User.id)
        .order_by(Report.created_at.desc())
        .limit(report_limit)
    ).all()

    for report, item, user in reports:
        activities.append(ActivityItem(
            id=str(report.id),
            type="report_filed",
            description=f"{user.name} reported '{item.title}' - {report.reason}",
            timestamp=report.created_at,
        ))

    # Auto-hidden items (system)
    hidden_items = session.exec(
        select(Item)
        .where(
            Item.is_hidden.is_(True),
            Item.hidden_reason == "auto_report_threshold",
        )
        .order_by(Item.created_at.desc())
        .limit(system_limit)
    ).all()

    for item in hidden_items:
        activities.append(ActivityItem(
            id=str(item.id),
            type="item_auto_hidden",
            description=f"Item '{item.title}' was auto-hidden due to multiple reports",
            timestamp=item.created_at,
        ))

    # Final merge
    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return activities[:limit]


@router.get("/claims", response_model=List[ClaimDetail])
def get_claims_for_moderation(
    status: Optional[Literal["pending", "approved", "rejected"]] = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_require_admin)
):
    """Get claims for moderation"""

    Owner = aliased(User)

    query = (
        select(Resolution, Item, User, Owner)
        .join(Item, Resolution.found_item_id == Item.id)
        .join(User, Resolution.claimant_id == User.id)
        .join(Owner, Item.user_id == Owner.id)
        .order_by(Resolution.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    if status:
        query = query.where(Resolution.status == status)

    results = session.exec(query).all()
    
    claims = []
    
    for resolution, item, claimer, owner in results:
        claims.append(ClaimDetail(
            id=str(resolution.id),
            item_id=str(item.id),
            item_title=item.title,
            item_owner_name=owner.name,
            item_owner_id=owner.public_id,
            claimer_name=claimer.name,
            claimer_id=claimer.public_id,
            claimer_email=claimer.email,
            status=resolution.status,
            created_at=resolution.created_at,
            claim_description=resolution.claim_description,
            decided_at=resolution.decided_at
        ))
    
    return claims


@router.get("/users", response_model=List[UserDetail])
def get_users_for_management(
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_require_admin)
):
    """Get all users with moderation info"""
    items_count_sq = (
        select(
            Item.user_id,
            func.count(Item.id).label("items_posted"),
        )
        .group_by(Item.user_id)
        .subquery()
    )

    # Count no. of reports received across all items posted by a user
    reports_count_sq = (
        select(
            Item.user_id,
            func.count(Report.id).label("reports_received"),
        )
        .join(Report, Report.item_id == Item.id)
        .group_by(Item.user_id)
        .subquery()
    )

    # COALESCE(x, 0) means, if no row exists, return 0 instead of NULL
    # Outer join to include users with zero items/reports
    rows = session.exec(
        select(
            User,
            func.coalesce(items_count_sq.c.items_posted, 0),
            func.coalesce(reports_count_sq.c.reports_received, 0),
        )
        .outerjoin(items_count_sq, items_count_sq.c.user_id == User.id)
        .outerjoin(reports_count_sq, reports_count_sq.c.user_id == User.id)
        .order_by(func.coalesce(reports_count_sq.c.reports_received, 0).desc())
        .limit(limit)
        .offset(skip)
    ).all()

    users = []

    for user, items_posted, reports_received in rows:
        users.append(UserDetail(
            id=user.id,
            public_id=user.public_id,
            name=user.name,
            email=user.email,
            image=user.image,
            created_at=user.created_at,
            warning_count=user.warning_count,
            is_banned=user.is_banned,
            ban_reason=user.ban_reason,
            ban_until=user.ban_until,
            items_posted=items_posted,
            reports_received=reports_received,
        ))

    return users


@router.post("/users/{user_id}/moderate")
def moderate_user(
    user_id: int,
    payload: ModerateUserRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_require_admin)
):
    """Moderate a user (warn, ban, unban)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if payload.action == "warn":
        user.warning_count += 1

        notification = Notification(
            user_id=user.id,
            title="Warning Issued",
            message=payload.reason or "You have received a warning from the admin team.",
            type="warning_issued",
        )

        try:
            session.add(notification)
            session.commit()
        except Exception:
            session.rollback()
            raise HTTPException(500, "Failed to issue warning")
    
    elif payload.action == "temp_ban":
        user.is_banned = True
        user.ban_reason = payload.reason or "Temporary ban by admin"
        days = payload.ban_days or 7
        user.ban_until = datetime.now(timezone.utc) + timedelta(days=days)
    
    # elif payload.action == "perm_ban":
    #     user.is_banned = True
    #     user.ban_reason = payload.reason or "Permanently banned by admin"
    #     user.ban_until = None
    
    elif payload.action == "unban":
        user.is_banned = False
        user.ban_reason = None
        user.ban_until = None
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(500, "Failed to moderate user")
    
    return {
        "ok": True,
        "message": f"User {payload.action} applied successfully"
    }

@router.get("/reported-items", response_model=List[ReportedItemDetail])
def get_reported_items(
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_require_admin)
):
    """Get all reported items"""

    Owner = aliased(User)
    Reporter = aliased(User)

    # Get items with reports count field appended
    # Returns list of (Item, Owner, report_count)
    items = session.exec(
        select(Item, Owner, func.count(Report.id).label("report_count"))
        .join(Report, Report.item_id == Item.id)
        .join(Owner, Item.user_id == Owner.id)
        .group_by(Item.id, Owner.id)
        .order_by(func.count(Report.id).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    if not items:
        return []
    
    item_ids = [item.id for item, _, _ in items]
    
    # Get all reports for these items
    # Returns list of (Report, User aka Reporter)
    reports = session.exec(
        select(Report, Reporter)
        .join(Reporter, Report.user_id == Reporter.id)
        .where(Report.item_id.in_(item_ids))
        .order_by(Report.created_at.desc())
    ).all()

    reports_by_item: dict[int, list[dict]] = {}

    # Organize reports under their respective items
    for report, reporters in reports:
        reports_by_item.setdefault(report.item_id, []).append({
            "id": report.id,
            "reporter_name": reporters.name,
            "reason": report.reason.capitalize(),
            "created_at": report.created_at.isoformat(),
            "status": report.status
        })

    reported_items = []
    
    for item, owner, report_count in items:
        reported_items.append(ReportedItemDetail(
            item_id=str(item.id),
            item_title=item.title,
            item_type=item.type,
            item_owner_name=owner.name,
            item_owner_id=owner.public_id,
            report_count=report_count,
            is_hidden=item.is_hidden,
            hidden_reason=item.hidden_reason,
            created_at=item.created_at,
            reports=reports_by_item.get(item.id, [])
        ))
    
    return reported_items


@router.post("/items/{item_id}/moderate")
async def moderate_item(
    item_id: uuid.UUID,
    payload: ModerateItemRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_require_admin)
):
    """Moderate an item (hide, restore, delete)"""
    user = get_db_user(session, admin)
    item = session.get(Item, item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if payload.action == "hide":
        item.is_hidden = True
        item.hidden_reason = "admin_moderation"
        
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise HTTPException(500, "Failed to hide item")
        
        return {
            "ok": True,
            "message": "Item hidden successfully"
        }
    
    elif payload.action == "restore":
        item.is_hidden = False
        item.hidden_reason = None
       
        # Mark all reports as reviewed
        session.exec(
            update(Report)
            .where(Report.item_id == item.id)
            .values(
                status="reviewed",
                reviewed_by=user.id,
                reviewed_at=datetime.now(timezone.utc),
            )
        )
        
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise HTTPException(500, "Failed to restore item")
        
        return {
            "ok": True, 
            "message": "Item restored successfully"
        }
    
    elif payload.action == "delete":
        try:
            session.delete(item)
            session.commit()
        except Exception:
            session.rollback()
            raise HTTPException(500, "Failed to delete item")

        return {
            "ok": True,
            "message": "Item deleted successfully"
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
