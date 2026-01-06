import os
from datetime import datetime, timedelta, timezone
from time import time
from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError, jwt
from sqlmodel import Session, select
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from app.db.db import get_session
from app.models.user import User
from app.schemas.auth_schemas import GoogleIDToken, RefreshTokenRequest, TokenResponse

router = APIRouter()

SECRET_KEY = os.environ["JWT_SECRET"]
CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]

if not CLIENT_ID or not SECRET_KEY:
    raise ValueError("Environment variables not set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # 30 minutes
MAX_SESSION_AGE_SECONDS = 24 * 60 * 60  # 24 hours


@router.post("/google", response_model=TokenResponse)
def google_auth(payload: GoogleIDToken, session: Session = Depends(get_session)):
    try:
        idinfo = id_token.verify_oauth2_token(payload.id_token, grequests.Request(), CLIENT_ID)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    # idinfo now trusted and parsed by Google libs
    google_id = idinfo["sub"]
    email = idinfo.get("email")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    # if email.split("@")[-1] != "nitc.ac.in":
    #     raise HTTPException(status_code=401, detail="Unauthorized domain")

    db_user = session.exec(
        select(User)
        .where(User.public_id == google_id)
    ).first()

    if db_user and db_user.is_banned:
        raise HTTPException(status_code=403, detail="User is banned")

    if not db_user:
        db_user = User(
            public_id=google_id,
            name=name,
            image=picture,
            email=email,
            role="user",
        )
        session.add(db_user)
        session.commit()

    session_start = int(time())
    expiry = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    jwt_payload = {
        "sub": db_user.public_id,
        "iat": datetime.now(timezone.utc),
        "exp": expiry,
        "session_start": session_start,
        "hostel": db_user.hostel,
        "role": db_user.role,
    }

    token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

    return TokenResponse(
        access_token=token, 
        expires_at=int(expiry.timestamp())
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, session: Session = Depends(get_session)):
    """
    Refresh an existing JWT token.
    Validates the current token and issues a new one if it's still valid.
    """
    try:
        # Decode the existing token (this will fail if token is invalid or expired)
        decoded = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])

        # Extract token structure info to validate
        session_start = decoded.get("session_start")
        if not session_start:
            raise HTTPException(status_code=401, detail="Invalid token structure")
        
        if not decoded.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token structure")

        # Check if the session is still valid
        if time() - session_start > MAX_SESSION_AGE_SECONDS:
            raise HTTPException(status_code=401, detail="Session expired")
        
        user = session.exec(
            select(User).where(User.public_id == decoded["sub"])
        ).first()

        if not user or user.is_banned:
            raise HTTPException(status_code=403, detail="User banned")
        
        # Create a new token with fresh expiration
        expiry = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        new_payload = {
            "sub": decoded["sub"],
            "iat": datetime.now(timezone.utc),
            "exp": expiry,
            "session_start": session_start,
            "role": decoded.get("role"),
        }
        
        new_token = jwt.encode(new_payload, SECRET_KEY, algorithm=ALGORITHM)

        return TokenResponse(
            access_token=new_token,
            expires_at=int(expiry.timestamp())
        )
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")
