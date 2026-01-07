import os
from sqlmodel import Session, create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    
    pool_pre_ping=True,
    pool_timeout=30,

    echo=True # Set echo to True for SQL query logging
)


def get_session():
    with Session(engine) as session:
        yield session
