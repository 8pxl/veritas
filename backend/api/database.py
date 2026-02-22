from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/nexus"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _enable_pg_trgm(dbapi_connection, connection_record):
    """Ensure the pg_trgm extension exists for fuzzy search."""
    with dbapi_connection.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    dbapi_connection.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

