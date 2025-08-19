from __future__ import annotations
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

load_dotenv()
from config.settings import DATABASE_URL

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "db" / "schema.sql"

def _split_sql(sql: str) -> list[str]:
    """
    Naive splitter: splits on semicolons that end a statement.
    Skips blank lines and psql meta-commands like \connect, \echo, etc.
    """
    lines = []
    for line in sql.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("--"):
            continue
        if s.startswith("\\"):
            continue
        lines.append(line)
    merged = "\n".join(lines)

    stmts = []
    buf = []
    for ch in merged:
        buf.append(ch)
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts

def main():
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")

    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    statements = _split_sql(sql)
    if not statements:
        print("No SQL statements found in schema.")
        return

    print(f"Applying {len(statements)} statements from {SCHEMA_FILE} …")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            for i, stmt in enumerate(statements, 1):
                conn.execute(text(stmt))
                print(f"  ✓ {i}/{len(statements)}")
        print("✅ Schema applied.")
    except SQLAlchemyError as e:
        print("❌ Failed applying schema:\n", str(e))

if __name__ == "__main__":
    main()
