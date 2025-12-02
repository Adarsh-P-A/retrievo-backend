from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import auth, items, lost_items, found_items, profile
from app.db.db import create_db_and_tables
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    try:
        create_db_and_tables()
        print("DB ready.")
    except Exception as e:
        print("ERROR: Cannot connect to DB:", e)
    yield
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(lost_items.router, prefix="/lost-item", tags=["Lost Items"])
app.include_router(found_items.router, prefix="/found-item", tags=["Found Items"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(items.router, prefix="/items", tags=["Items"])


@app.get("/")
def root():
    return {"status": "ok"}
