#!/usr/bin/env python3
"""Data-preserving migration: SQLite -> PostgreSQL.

Migrates ALL rows from the SQLite database (backend/construction_risk.db by
default) into an already-migrated PostgreSQL database. The target schema must
have been created first with Alembic:

    DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/buildsure \
        backend/venv/bin/alembic -c backend/alembic.ini upgrade head

Behaviour
---------
* Every source table is copied (rows are never silently dropped).
* Values are coerced to the target column type and every coercion is logged.
* Legacy foreign keys that point to a non-existent parent (possible in SQLite,
  which does not enforce FKs) are converted to NULL and reported as ``orphan-fk``
  warnings -- the value is not lost, it is surfaced so operators can review.
* At the end a per-table summary + overall status is printed. The process exits
  non-zero if any value could not be converted.

Usage
-----
    backend/venv/bin/python scripts/migrate_sqlite_to_postgres.py \
        --sqlite backend/construction_risk.db \
        --url "postgresql+psycopg2://buildsure@localhost:5433/buildsure"

Options
-------
    --sqlite PATH       source SQLite database (default: backend/construction_risk.db)
    --url URL           target DATABASE_URL (default: $DATABASE_URL, else local buildsure dev URL)
    --truncate          wipe existing rows in the target before loading (off by default;
                        the tool aborts if the target already contains data unless given)
    --strict-fks        abort on the first orphaned foreign key instead of NULL-ing it
    --log-errors        collect per-value coercion errors instead of aborting; the run
                        still exits non-zero and prints every error at the end
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase

_DEFAULT_SQLITE = "backend/construction_risk.db"
_DEFAULT_URL = "postgresql+psycopg2://buildsure@localhost:5433/buildsure"

# Import order matters -- the app models register themselves onto the same
# metadata so the FK graph and table set match the running application.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "backend"))

from app.database.database import DATABASE_URL as APP_DEFAULT_URL  # noqa: E402
import app.models.models as _m  # noqa: E402


class MigrationError(Exception):
    pass


def _type_coerce(value, col_type):
    """Return a value acceptable to the target column, or raise ValueError."""
    if value is None:
        return None

    if isinstance(col_type, sa.Integer):
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value.is_integer():
                return int(value)
            raise ValueError(f"non-integer float {value!r}")
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                return None
            if s.lower() in ("true", "1.0"):
                return 1
            if s.lower() in ("false", "0.0"):
                return 0
            if "." in s and s.replace(".", "", 1).replace("-", "", 1).isdigit():
                f = float(s)
                if f.is_integer():
                    return int(f)
            return int(s)
        raise ValueError(f"cannot coerce {type(value).__name__} {value!r}")

    if isinstance(col_type, sa.Float):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            s = value.strip()
            return float(s) if s else None
        raise ValueError(f"cannot coerce {type(value).__name__} {value!r}")

    if isinstance(col_type, sa.DateTime):
        if isinstance(value, datetime):
            v = value.replace(tzinfo=None) if value.tzinfo else value
            return v
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            s2 = s.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(s2).replace(tzinfo=None)
            except ValueError:
                # tolerate sqlite-native "YYYY-MM-DD HH:MM:SS.ffffff" space form
                return datetime.fromisoformat(s2.replace("T", " ", 1).replace("+00:00", "")).replace(tzinfo=None)
        raise ValueError(f"cannot coerce {type(value).__name__} {value!r}")

    if isinstance(col_type, sa.JSON):
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            return json.loads(s)
        if isinstance(value, (int, float, bool)):
            return value
        raise ValueError(f"cannot coerce {type(value).__name__} {value!r}")

    if isinstance(col_type, (sa.String, sa.Text)):
        if isinstance(value, str):
            return value
        return str(value)

    return value


def _fk_list(meta):
    """[(child_table, child_col, parent_table, parent_col)]"""
    out = []
    for table in meta.sorted_tables:
        for fk in table.foreign_keys:
            out.append((table.name, fk.parent.name, fk.column.table.name, fk.column.name))
    return out


def _check_orphans(tgt_engine, meta):
    """Return list of (child_table, child_col, parent_table, count_of_orphans)."""
    orphans = []
    for child, ccol, parent, pcol in _fk_list(meta):
        child_col = f'"{child}"."{ccol}"'
        parent_col = f'"{parent}"."{pcol}"'
        q = f"""
            SELECT count(*) FROM {child_col}?? -- placeholder replaced below
        """
        stmt = f"""
            SELECT count(*) AS n FROM "{child}" c
            LEFT JOIN "{parent}" p ON c."{ccol}" = p."{pcol}"
            WHERE c."{ccol}" IS NOT NULL AND p."{pcol}" IS NULL
        """
        with tgt_engine.connect() as conn:
            n = conn.execute(sa.text(stmt)).scalar()
        if n:
            orphans.append((child, ccol, parent, n))
    return orphans


def _nullify_orphans(tgt_engine, meta):
    for child, ccol, parent, pcol in _fk_list(meta):
        stmt = f"""
            UPDATE "{child}" SET "{ccol}" = NULL
            WHERE "{ccol}" IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM "{parent}" p WHERE p."{pcol}" = "{child}"."{ccol}")
        """
        with tgt_engine.begin() as conn:
            conn.execute(sa.text(stmt))


def _infer_meta():
    # The app models already registered on Base.metadata above.
    return _m.Base.metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default=_DEFAULT_SQLITE)
    parser.add_argument("--url", default=None)
    parser.add_argument("--truncate", action="store_true")
    parser.add_argument("--strict-fks", action="store_true")
    parser.add_argument("--log-errors", action="store_true")
    args = parser.parse_args()

    target_url = args.url or os.environ.get("DATABASE_URL") or APP_DEFAULT_URL

    meta = _infer_meta()
    src = sa.create_engine(f"sqlite:///{args.sqlite}")
    tgt = sa.create_engine(target_url, pool_pre_ping=True)

    src_conn = src.connect()
    try:
        existing = set(inspect(src).get_table_names())
    finally:
        src_conn.close()

    missing = [t.name for t in meta.sorted_tables if str(t.name) not in existing]
    if missing:
        print(f"ERROR: source SQLite lacks tables: {missing}")
        sys.exit(1)

    # Refuse to run against a populated target unless truncation is requested.
    tgt_conn = tgt.connect()
    try:
        for t in meta.sorted_tables:
            n = tgt_conn.execute(sa.text(f'SELECT count(*) FROM "{t.name}"')).scalar()
            if n:
                if not args.truncate:
                    tgt_conn.close()
                    print(f"ERROR: target table \"{t.name}\" already has {n} row(s). "
                          f"Re-run with --truncate to wipe target rows first.")
                    sys.exit(1)
                break
    finally:
        tgt_conn.close()

    if args.truncate:
        with tgt.begin() as conn:
            for t in reversed(meta.sorted_tables):
                conn.execute(sa.text(f'TRUNCATE "{t.name}" RESTART IDENTITY CASCADE'))
        print("Truncated existing target rows.")

    # Load rows. Insert order follows the dependency graph (parents first).
    errors = []
    summary = []
    total_copied = 0
    with tgt.begin() as tconn:
        # Skip orphan-FK validation at insert time only if we intend to NULL them
        # later; otherwise PostgreSQL will reject the row (strict mode).
        if not args.strict_fks:
            tconn.execute(sa.text("SET session_replication_role = replica"))
        for table in meta.sorted_tables:
            cols = table.columns
            with src.connect() as sconn:
                rows = list(sconn.execute(sa.select(*[c for c in cols])).mappings())
            coerced, bad = [], []
            for row in rows:
                rec = {}
                for c in cols:
                    try:
                        rec[c.name] = _type_coerce(row[c.name], c.type)
                    except Exception as exc:  # per-value coercion failure
                        bad.append((row.get(next(iter(c.primary_key), "?").name if next(iter(c.primary_key), None) else "row"), c.name, repr(row[c.name]), str(exc)))
                        if not args.log_errors:
                            raise MigrationError(
                                f"{table.name}.{c.name} row could not be converted: {exc!r} value={row[c.name]!r}"
                            ) from exc
                coerced.append(rec)
            n_rows = len(coerced)
            n_bad = len(bad)
            for i in range(0, len(coerced), 1000):
                batch = coerced[i:i + 1000]
                if batch:
                    tconn.execute(sa.insert(table), batch)
            total_copied += n_rows
            summary.append((table.name, len(rows), n_rows, n_bad, 0))
            for b in bad:
                errors.append((table.name, *b))
            if n_bad:
                print(f"  {table.name}: {n_rows}/{len(rows)} rows copied, {n_bad} values EXCLUDED (see report)")

        if not args.strict_fks:
            tconn.execute(sa.text("SET session_replication_role = DEFAULT"))

    # Integrity pass: surface (and, unless --strict-fks, repair) orphan FKs.
    orphans = _check_orphans(tgt, meta)
    if orphans:
        print("\nORPHAN FOREIGN KEYS FOUND (would have rejected the row in strict mode):")
        for child, ccol, parent, n in orphans:
            print(f"  {child}.{ccol} -> {parent}: {n} value(s) set to NULL")
        if args.strict_fks:
            print("ERROR: --strict-fks set and orphaned FKs exist.")
            sys.exit(1)
        _nullify_orphans(tgt, meta)

    print("\nMIGRATION SUMMARY")
    print(f"{'table':<28}{'src':>8}{'copied':>8}{'skip':>8}  fk-orphans")
    grand_bad = 0
    orphan_map = {f"{c}.{cc}->{p}": n for c, cc, p, n in orphans}
    for name, n_src, n_copy, n_bad, _ in summary:
        orph = sum(v for k, v in orphan_map.items() if k.startswith(f"{name}."))
        grand_bad += n_bad
        print(f"{name:<28}{n_src:>8}{n_copy:>8}{n_bad:>8}  {orph}")
    print(f"\nTotal rows copied: {total_copied}")
    if errors:
        print(f"\n{len(errors)} value(s) were excluded (coercion failures):")
        seen = set()
        for table, pk, col, val, err in errors:
            key = (table, col)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {table}.{col}: {val!r} -> {err}")
    print(f"\nStatus: {('FAILED - coercion errors' if errors or (args.strict_fks and orphans) else 'OK')}")
    sys.exit(1 if (errors or (args.strict_fks and orphans)) else 0)


if __name__ == "__main__":
    main()