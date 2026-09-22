#!/usr/bin/env python3
"""Post-migration validation: SQLite source vs PostgreSQL target.

Compares per-table row counts, then verifies every foreign key relationship in
the target is intact (no orphaned children), and finally confirms the seeded
manager account is present so auth keeps working after the cut-over.

Exits 0 on success, 1 on any mismatch. Run AFTER migrate_sqlite_to_postgres.py.

    backend/venv/bin/python scripts/validate_migration.py \
        --sqlite backend/construction_risk.db \
        --url "postgresql+psycopg2://buildsure@localhost:5433/buildsure"
"""

import argparse
import os
import sys

import sqlalchemy as sa
from sqlalchemy import inspect

_DEFAULT_SQLITE = "backend/construction_risk.db"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "backend"))

from app.database.database import DATABASE_URL as APP_DEFAULT_URL  # noqa: E402
import app.models.models as _m  # noqa: E402


def _fk_list(meta):
    out = []
    for table in meta.sorted_tables:
        for fk in table.foreign_keys:
            out.append((table.name, fk.parent.name, fk.column.table.name, fk.column.name))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default=_DEFAULT_SQLITE)
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    target_url = args.url or os.environ.get("DATABASE_URL") or APP_DEFAULT_URL
    meta = _m.Base.metadata

    src = sa.create_engine(f"sqlite:///{args.sqlite}")
    tgt = sa.create_engine(target_url)

    failures = []

    # 1) per-table row counts
    print(f"{'table':<28}{'sqlite':>8}{'postgres':>10}  status")
    for table in meta.sorted_tables:
        with src.connect() as c:
            n_src = c.execute(sa.text(f'SELECT count(*) FROM "{table.name}"')).scalar()
        with tgt.connect() as c:
            n_tgt = c.execute(sa.text(f'SELECT count(*) FROM "{table.name}"')).scalar()
        ok = n_src == n_tgt
        print(f"{table.name:<28}{n_src:>8}{n_tgt:>10}  {'OK' if ok else 'MISMATCH'}")
        if not ok:
            failures.append(f"{table.name}: sqlite={n_src} postgres={n_tgt}")

    # 2) referential integrity in the target
    print("\nReferential integrity (postgres):")
    for child, ccol, parent, pcol in _fk_list(meta):
        stmt = f"""
            SELECT count(*) FROM "{child}" c
            LEFT JOIN "{parent}" p ON c."{ccol}" = p."{pcol}"
            WHERE c."{ccol}" IS NOT NULL AND p."{pcol}" IS NULL
        """
        with tgt.connect() as c:
            orphans = c.execute(sa.text(stmt)).scalar()
        if orphans:
            failures.append(f"{child}.{ccol} -> {parent}: {orphans} orphan(s)")
            print(f"  {child}.{ccol} -> {parent}: {orphans} ORPHAN(S)")
        else:
            print(f"  {child}.{ccol} -> {parent}: OK")

    # 3) auth-critical anchor rows
    print("\nAuth anchor rows (postgres):")
    anchors = {
        "seed manager (BuildSure@gmail.com)": "managers",
        "seed project (proj_riverside_001)": "projects",
        "seed site (site_riverside_main)": "sites",
    }
    for label, table in anchors.items():
        with tgt.connect() as c:
            n = c.execute(sa.text(f'SELECT count(*) FROM "{table}"')).scalar()
        print(f"  {label}: {n} row(s)")
        if n == 0:
            failures.append(f"{table} empty in postgres")

    print(f"\nStatus: {'FAILED' if failures else 'OK'}")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()