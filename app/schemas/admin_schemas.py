# Response Models
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_items: int
    items_this_month: int
    items_last_month: int
    
    claims_approved_this_month: int
    claims_approved_last_month: int
    claims_rejected_this_month: int
    claims_rejected_last_month: int
    claims_pending: int

    active_reports: int
    reports_this_month: int
    reports_last_month: int

    total_users: int
    users_this_month: int
    users_last_month: int


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