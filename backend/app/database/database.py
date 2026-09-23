from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

import os

from dotenv import load_dotenv, find_dotenv
from urllib.parse import quote_plus

_dir = os.path.dirname(os.path.abspath(__file__))
_default_db = os.path.join(_dir, '..', '..', 'construction_risk.db')
load_dotenv(find_dotenv())

# Enterprise override: point the platform at any SQLAlchemy URL via DATABASE_URL,
# e.g. postgresql+psycopg2://user:pass@host:5432/buildsure                  (prod)
#      sqlite:///<path>/construction_risk.db                                (dev/test)
# Container operators may instead pass libpq-style vars (PGHOST/PGPORT/PGUSER/
# PGPASSWORD/PGDATABASE); the DSN is assembled here with the password
# URL-encoded so special characters (e.g. '@') never corrupt the connection
# string.
DATABASE_URL = os.environ.get("DATABASE_URL") or (
    f"postgresql+psycopg2://{os.environ.get('PGUSER', 'buildsure')}:"
    f"{quote_plus(os.environ.get('PGPASSWORD', ''))}@"
    f"{os.environ.get('PGHOST', 'localhost')}:{os.environ.get('PGPORT', '5432')}/"
    f"{os.environ.get('PGDATABASE', 'buildsure')}"
    if os.environ.get("PGHOST")
    else f"sqlite:///{_default_db}"
)

_IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# SQLite requires a shared-thread connection; PostgreSQL drivers reject the
# unknown ``check_same_thread`` kwarg, so the option is applied per-DBAPI.
_engine_kwargs = {}
if _IS_POSTGRES:
    # Fail fast on stale pooled connections and avoid autocommit surprises.
    _engine_kwargs["pool_pre_ping"] = True
else:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added to existing tables after their original creation. ``create_all``
# never mutates an existing table, so lightweight ALTER TABLE statements keep the
# schema in sync with the models on upgrade.
_MIGRATION_COLUMNS = {
    "monitoring_events": ["analysis_id"],
    "hazards": ["analysis_id"],
    "risk_assessments": ["analysis_id"],
    "recommendations": ["analysis_id"],
    "equipment": ["analysis_id"],
    "workers": ["analysis_id"],
    "safety_violations": ["analysis_id"],
    "safety_alerts": ["analysis_id"],
    "safety_assessments": ["analysis_id"],
}


def _migrate():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _MIGRATION_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col in columns:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR(64)"))


def init_db():
    from app.models import models  # noqa: ensure all models registered
    Base.metadata.create_all(bind=engine)
    _migrate()
