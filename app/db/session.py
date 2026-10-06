from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def database(settings):
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=5,
        connect_args={"connect_timeout": 3},
    )
    return engine, sessionmaker(engine, expire_on_commit=False)


def get_db(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def lock(db, key: str):
    # Locks PostgreSQL por chave, liberados automaticamente no commit/rollback.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})
