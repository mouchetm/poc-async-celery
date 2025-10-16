from sqlmodel import SQLModel, Session, create_engine
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/chatdb"
)

# For PostgreSQL, we need to handle thread safety
connect_args = {}
if "postgresql" in DATABASE_URL:
    # PostgreSQL doesn't need connect_args like SQLite does
    pass
elif "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)


def get_session():
    with Session(engine) as session:
        yield session
