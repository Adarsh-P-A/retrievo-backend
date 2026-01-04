import os
from sqlmodel import Session, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", 'postgresql://postgres:postgres@localhost:5432/retrievo_db')

engine = create_engine(DATABASE_URL, echo=True) # Set echo to True for SQL query logging


def get_session():
    with Session(engine) as session:
        yield session
