from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db.db import get_session
from app.models.found_item import FoundItem
from app.models.lost_item import LostItem
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
    if (item_type == "lost"):
        item = session.get(LostItem, item_id)
        if not item:
            return {"error": "Lost item not found"}
        return item
    elif (item_type == "found"):
        item = session.get(FoundItem, item_id)
        if not item:
            return {"error": "Found item not found"}
        return item
    else:
        return {"ok": False, "error": "Invalid item type"}
