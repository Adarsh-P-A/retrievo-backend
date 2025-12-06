from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.db import get_session
from app.models.found_item import FoundItem
from app.models.lost_item import LostItem
from app.models.user import User
from app.utils.auth_helper import get_current_user


router = APIRouter()


@router.get("/all")
async def get_all_items(session: Session = Depends(get_session)):
    lost_items = session.exec(
        select(LostItem).order_by(LostItem.created_at.desc())
    ).all()
    found_items = session.exec(
        select(FoundItem).order_by(FoundItem.created_at.desc())
    ).all()

    return {
        "lost_items": lost_items,
        "found_items": found_items,
    }


@router.get("/{item_id}/{item_type}")
async def get_item(
    item_id: int,
    item_type: str,
    session: Session = Depends(get_session),
):
    if item_type not in ["lost", "found"]:
        raise HTTPException(400, "Invalid item type")

    Type = LostItem if item_type == "lost" else FoundItem

    statement = (
        select(Type, User)
        .join(User, User.id == Type.user_id)
        .where(Type.id == item_id)
    )

    result = session.exec(statement).first()

    if not result:
        raise HTTPException(404, f"{item_type.capitalize()} item not found")

    item, user = result

    return {
        "item": item,
        "reporter": {
            "public_id": user.public_id,
            "name": user.name,
            "image": user.image,
        }
    }
