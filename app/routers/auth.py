import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from jose import jwt
from sqlmodel import Session, select

from app.db.db import get_session
from app.models.users import User

router = APIRouter()

SECRET_KEY = os.getenv("JWT_SECRET", 'your_really_long_secret_key')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day


class GoogleAuthPayload(BaseModel):
    email: str
    name: str
    picture: str
    google_id: str


class TokenResponse(BaseModel):
    access_token: str
    user_id: str


@router.post("/google", response_model=TokenResponse)
def google_auth(payload: GoogleAuthPayload, session: Session = Depends(get_session),):
    db_user = session.exec(
        select(User).where(User.google_id == payload.google_id)
    ).first()

    if not db_user:
        db_user = User(
            google_id=payload.google_id,
            name=payload.name,
            profile_picture=payload.picture,
            email=payload.email,
            role="user"  # Default role
        )
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    expiry = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    jwt_payload = {
        "sub": str(db_user.id),
        "role": db_user.role,
        "iat": datetime.now(timezone.utc),
        "exp": expiry,
    }

    token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

    return TokenResponse(
        access_token=token,
        user_id=str(db_user.id),
    )
