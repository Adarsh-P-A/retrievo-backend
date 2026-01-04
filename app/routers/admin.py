from typing import Literal, Optional, List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, and_, update
from sqlalchemy.orm import aliased
from pydantic import BaseModel
import uuid

from app.db.db import get_session
from app.models.user import User
from app.models.item import Item
from app.models.resolution import Resolution
from app.models.report import Report
from app.utils.auth_helper import get_current_user_required

router = APIRouter()


# Response Models
class OverviewStats(BaseModel):
    total_items: int
    items_current_month: int
    claims_approved_current_month: int
    claims_rejected_current_month: int
    claims_pending: int
    active_reports: int
    reports_current_month: int


class ActivityItem(BaseModel):
    id: str
    type: str  # "claim_approved", "claim_rejected", "claim_pending", "report_filed", "item_auto_hidden"
    description: str
    timestamp: datetime
    metadata: dict


class ClaimDetail(BaseModel):
    id: str
    item_id: str
    item_title: str
    item_owner_name: str
    item_owner_id: str
    claimer_name: str
    claimer_id: str
    claimer_email: str
    status: str
    created_at: datetime
    claim_description: str
    decided_at: Optional[datetime]


class UserDetail(BaseModel):
    id: int
    public_id: str
    name: str
    email: str
    image: str
    created_at: datetime
    warning_count: int
    is_banned: bool
    ban_reason: Optional[str]
    ban_until: Optional[datetime]
    items_posted: int
    reports_received: int


class ReportedItemDetail(BaseModel):
    item_id: str
    item_title: str
    item_type: str
    item_owner_name: str
    item_owner_id: str
    report_count: int
    is_hidden: bool
    hidden_reason: Optional[str]
    created_at: datetime
    reports: List[dict]


class InsightData(BaseModel):
    most_reported_items: List[dict]
    most_reported_users: List[dict]
    claim_success_rate: float
    avg_claim_resolution_time_hours: Optional[float]
    items_by_category: List[dict]
    claims_by_status: dict


class ModerateUserRequest(BaseModel):
    action: str  # "warn", "temp_ban", "perm_ban", "unban"
    reason: Optional[str] = None
    ban_days: Optional[int] = None


class ModerateItemRequest(BaseModel):
    action: str  # "hide", "restore", "delete"
    reason: Optional[str] = None


def require_admin(user: User = Depends(get_current_user_required)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/stats", response_model=OverviewStats)
def get_overview_stats(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    """Get overview statistics for the admin dashboard"""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Items
    total_items, items_current = session.exec(
        select(
            func.count(Item.id),
            func.count().filter(Item.created_at >= month_start),
        )
    ).one()

    # Claims
    claims_approved, claims_rejected, claims_pending = session.exec(
        select(
            func.count().filter(
                and_(
                    Resolution.status == "approved",
                    Resolution.decided_at >= month_start,
                )
            ),
            func.count().filter(
                and_(
                    Resolution.status == "rejected",
                    Resolution.decided_at >= month_start,
                )
            ),
            func.count().filter(Resolution.status == "pending"),
        )
    ).one()

    # Reports
    active_reports, reports_current = session.exec(
        select(
            func.count().filter(Report.status == "pending"),
            func.count().filter(Report.created_at >= month_start),
        )
    ).one()

    return OverviewStats(
        total_items=total_items,
        items_current_month=items_current,
        claims_approved_current_month=claims_approved,
        claims_rejected_current_month=claims_rejected,
        claims_pending=claims_pending,
        active_reports=active_reports,
        reports_current_month=reports_current,
    )


@router.get("/activity", response_model=List[ActivityItem])
def get_recent_activity(
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
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
            metadata={
                "item_id": str(item.id),
                "claimer_id": user.public_id,
                "resolution_id": str(res.id),
            },
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
            metadata={
                "item_id": str(item.id),
                "reporter_id": user.public_id,
                "reason": report.reason,
            },
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
            metadata={"item_id": str(item.id)},
        ))

    # Final merge
    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return activities[:limit]


@router.get("/claims", response_model=List[ClaimDetail])
def get_claims_for_moderation(
    status: Literal["pending", "approved", "rejected", None],
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    """Get claims for moderation"""

    Owner = aliased(User)

    query = (
        select(Resolution, Item, User, Owner)
        .join(Item, Resolution.found_item_id == Item.id)
        .join(User, Resolution.claimant_id == User.id)
        .join(Owner, Item.user_id == Owner.id)
        .order_by(Resolution.created_at.desc())
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
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
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

    reports_count_sq = (
        select(
            Item.user_id,
            func.count(Report.id).label("reports_received"),
        )
        .join(Report, Report.item_id == Item.id)
        .group_by(Item.user_id)
        .subquery()
    )

    rows = session.exec(
        select(
            User,
            func.coalesce(items_count_sq.c.items_posted, 0),
            func.coalesce(reports_count_sq.c.reports_received, 0),
        )
        .outerjoin(items_count_sq, items_count_sq.c.user_id == User.id)
        .outerjoin(reports_count_sq, reports_count_sq.c.user_id == User.id)
        .order_by(func.coalesce(reports_count_sq.c.reports_received, 0).desc())
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
    admin: User = Depends(require_admin)
):
    """Moderate a user (warn, ban, unban)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if payload.action == "warn":
        user.warning_count += 1
    
    elif payload.action == "temp_ban":
        user.is_banned = True
        user.ban_reason = payload.reason or "Temporary ban by admin"
        days = payload.ban_days or 7
        user.ban_until = datetime.now(timezone.utc) + timedelta(days=days)
    
    elif payload.action == "perm_ban":
        user.is_banned = True
        user.ban_reason = payload.reason or "Permanently banned by admin"
        user.ban_until = None
    
    elif payload.action == "unban":
        user.is_banned = False
        user.ban_reason = None
        user.ban_until = None
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    try:
        session.add(user)
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
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
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
            "reason": report.reason,
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
def moderate_item(
    item_id: uuid.UUID,
    payload: ModerateItemRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin)
):
    """Moderate an item (hide, restore, delete)"""    
    item = session.get(Item, item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if payload.action == "hide":
        item.is_hidden = True
        item.hidden_reason = payload.reason or "admin_moderation"
        
        try:
            session.add(item)
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
                reviewed_by=admin.id,
                reviewed_at=datetime.now(timezone.utc),
            )
        )
        
        try:
            session.add(item)
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
