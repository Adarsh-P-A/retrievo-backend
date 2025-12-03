from sqlmodel import Session, create_engine

DATABASE_URL = (
    "postgresql://postgres:postgres@localhost:5432/retrievo_db"
)

engine = create_engine(DATABASE_URL, echo=True)


def get_session():
    with Session(engine) as session:
        yield session
