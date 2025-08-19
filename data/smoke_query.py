from __future__ import annotations
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

with engine.begin() as conn:
    rows = conn.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog','information_schema')
        ORDER BY 1,2
    """)).fetchall()

print("User tables (first 20):")
for r in rows[:20]:
    print(" -", f"{r.table_schema}.{r.table_name}")
