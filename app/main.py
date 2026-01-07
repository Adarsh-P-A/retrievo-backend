import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, items, notifications, profile, resolutions, admin

app = FastAPI()

origins = set([
    "http://localhost:3000",
    os.getenv("FRONTEND_URL")
])

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in origins if origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(items.router, prefix="/items", tags=["Items"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(resolutions.router, prefix="/resolutions", tags=["Resolutions"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


@app.get("/")
def root():
    return {"status": "ok"}
