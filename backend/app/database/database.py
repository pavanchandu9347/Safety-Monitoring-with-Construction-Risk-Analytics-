from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

import os

_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(_dir, '..', '..', 'construction_risk.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
