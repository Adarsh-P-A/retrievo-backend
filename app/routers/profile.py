from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.db import get_session
from app.models.item import Item
from app.models.user import User
from app.utils.auth_helper import get_current_user_optional, get_current_user_required, get_db_user
from app.utils.s3_service import get_all_urls
from app.schemas.profile_schemas import PhoneSetPayload, HostelSetPayload


router = APIRouter()

@router.post("/set-hostel")
async def set_hostel(
    payload: HostelSetPayload,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    if payload.hostel not in ['boys', 'girls']:
        raise HTTPException(status_code=400, detail="Invalid hostel option")

    user.hostel = payload.hostel
    
    session.commit()
    session.refresh(user)

    return {"ok": True}

@router.post("/set-phone")
async def set_phone(
    payload: PhoneSetPayload,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    if user.phone:
        raise HTTPException(
            status_code=403,
            detail="Phone number already set"
        )

    user.phone = payload.phone

    session.commit()
    session.refresh(user)

    return {"ok": True}

@router.get("/me")
async def get_my_profile(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    return get_db_user(session, current_user)


@router.get("/items")
async def get_my_items(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    items = session.exec(
        select(Item)
        .where(Item.user_id == user.id)
        .order_by(Item.created_at.desc())
    ).all()

    # Separate by type
    lost_items = [item for item in items if item.type == "lost"]
    found_items = [item for item in items if item.type == "found"]

    return {
        "lost_items": get_all_urls(lost_items),
        "found_items": get_all_urls(found_items),
    }


@router.get("/{public_id}")
async def get_profile(
    public_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Fetch profile user (the user being viewed)
    profile_user = session.exec(
        select(User).where(User.public_id == public_id)
    ).first()

    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Determine viewer's hostel (if logged in)
    hostel = None
    
    if current_user:
        viewer = session.exec(
            select(User).where(User.public_id == current_user["sub"])
        ).first()

        if viewer:
            hostel = viewer.hostel

    # Build item query
    query = select(Item).where(Item.user_id == profile_user.id)

    if hostel:
        query = query.where((Item.visibility == hostel) | (Item.visibility == "public"))
    else:
        query = query.where(Item.visibility == "public")

    items = session.exec(query).all()

    lost_items = [item for item in items if item.type == "lost"]
    found_items = [item for item in items if item.type == "found"]

    return {
        "user": {
            "name": profile_user.name,
            "email": profile_user.email,
            "image": profile_user.image,
            "created_at": profile_user.created_at,
        },
        "lost_items": get_all_urls(lost_items),
        "found_items": get_all_urls(found_items),
    }