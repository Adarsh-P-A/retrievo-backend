import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, func, select
from sqlalchemy.exc import IntegrityError

from app.db.db import get_session
from app.models.item import Item
from app.models.resolution import Resolution
from app.models.user import User
from app.utils.auth_helper import get_current_user_optional, get_current_user_required, get_db_user
from app.utils.s3_service import compress_image, delete_s3_object, generate_signed_url, get_all_urls, upload_to_s3
from app.models.report import Report
from app.models.notification import Notification
from app.utils.form_validator import validate_create_item_form
from app.schemas.items_schemas import *


router = APIRouter()

MAX_UPLOAD_SIZE_MB = 3
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/create")
async def add_item(
    item_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    visibility: str = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    data = validate_create_item_form(
        item_type=item_type,
        title=title,
        description=description,
        category=category,
        date=date,
        location=location,
        visibility=visibility,
    )

    # read image into memory and upload
    raw_bytes = await image.read()

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"Image exceeds {MAX_UPLOAD_SIZE_MB}MB limit")

    buffer, ext = compress_image(raw_bytes)
    s3_key = upload_to_s3(buffer, ext, image.filename)

    # user lookup
    user = get_db_user(session, current_user)

    # create DB item
    db_item = Item(
        user_id=user.id,
        title=data.title,
        description=data.description,
        category=data.category,
        date=data.date,
        location=data.location,
        type=data.item_type,
        visibility=data.visibility,
        image=s3_key,
    )

    session.add(db_item)
    session.commit()
    session.refresh(db_item)

    return db_item.id


@router.get("/all")
async def get_all_items(
    page: int = 1,
    limit: int = 10,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Get user's hostel if logged in
    hostel = current_user.get("hostel") if current_user else None

    # Query all items
    query = (
        select(Item)
        .where(Item.is_hidden == False)
        .order_by(Item.created_at.desc())
    )

    # apply visibility filters based on user's hostel
    if hostel:
        query = query.where((Item.visibility == hostel) | (Item.visibility == 'public'))
    else:
        query = query.where(Item.visibility == 'public')

    # Get total count for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # fetch items
    items = session.exec(query).all()

    items_response = get_all_urls(items)

    return {
        "items": items_response,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": offset + len(items) < total,
    }


@router.get("/{item_id}")
async def get_item(
    item_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Get user's hostel if logged in
    hostel = current_user.get("hostel") if current_user else None

    # Check if user is admin (admins can view all items)
    is_admin = current_user.get("role") == "admin" if current_user else False

    query = (
        select(Item, User, Resolution.status)
        .join(User, User.id == Item.user_id)
        .outerjoin(
            Resolution,
            (Resolution.found_item_id == Item.id)
            & (Resolution.status.in_(["pending", "approved"]))
        )
        .where(Item.id == item_id)
    )

    if not is_admin:
        query = query.where(Item.is_hidden == False)

    result = session.exec(query).first()
    if not result:
        raise HTTPException(404, "Item not found")
    
    item, user, claim_status = result
    claim_status = claim_status or "none"

    # visibility check
    if item.visibility != "public" and item.visibility != hostel:
        raise HTTPException(403, "Unauthorized to view this item")

    item_dict = item.model_dump()
    item_dict["image"] = generate_signed_url(item.image)

    return {
        "item": item_dict,
        "reporter": {
            "public_id": user.public_id,
            "name": user.name,
            "image": user.image,
        },
        "claim_status": claim_status,
    }

@router.patch("/{item_id}")
async def update_item(
    item_id: uuid.UUID,
    updates: ItemUpdateSchema,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    query = (
        select(Item, Resolution.id)
        .outerjoin(
            Resolution,
            (Resolution.found_item_id == Item.id)
            & (Resolution.status.in_(["pending", "approved"]))
        )
        .where(Item.id == item_id)
        .where(Item.is_hidden == False)
    )

    result = session.exec(query).first()
    if not result:
        raise HTTPException(status_code=404, detail="Item not found")

    item, active_resolution_id = result
    
    if active_resolution_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot update item while it has a pending or approved claim",
        )

    user = get_db_user(session, current_user)
    if not user or item.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to update this item")

    update_data = updates.model_dump(exclude_unset=True) # only get provided fields (skip None fields)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    for field, value in update_data.items():
        setattr(item, field, value)

    session.commit()

    return item.id

@router.delete("/{item_id}")
async def delete_item(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    item = session.exec(
        select(Item)
        .where(Item.id == item_id)
        .where(Item.is_hidden is False)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # ownership check
    user = get_db_user(session, current_user)

    if not user or item.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to delete this item",
        )
    
    delete_s3_object(item.image)

    session.delete(item)
    session.commit()

    return { "ok": True }

@router.post("/{id}/report")
async def report_item(
    id: uuid.UUID,
    payload: ReportCreateSchema,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):  
    item = session.exec(
        select(Item)
        .where(Item.id == id)
        .where(Item.is_hidden == False)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Only logged in users can report
    user = get_db_user(session, current_user)
    if not user:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # prevent self-reporting
    if item.user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot report your own item")

    # Create report
    report = Report(
        user_id=user.id,
        item_id=item.id,
        reason=payload.reason,
    )

    session.add(report)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="You have already reported this item")

    # Moderation Logic

    report_count = session.exec(
        select(func.count(Report.id))
        .where(Report.item_id == item.id)
        .where(Report.status == "pending")
    ).first()

    if report_count >= 5:
        item.is_hidden = True
        item.hidden_reason = "auto_report_threshold"

        # Notify owner about hiding
        notification = Notification(
            user_id=item.user_id,
            type="system_notice",
            title="Your item has been hidden",
            message=f"Your item '{item.title}' has been hidden due to multiple reports from users.",
            item_id=item.id,
        )

        session.add(notification)
        session.commit()

        # TODO: Increment warning count for user and ban if necessary

    return { "ok": True }
