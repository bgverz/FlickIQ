from __future__ import annotations
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
from config.settings import DATABASE_URL

def peek(qualified: str):
    if "." not in qualified:
        print('Usage: python -m data.peek_table <schema.table>, e.g., public.item_embeddings')
        sys.exit(2)
    schema, table = qualified.split(".", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        cols = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
        """), {"schema": schema, "table": table}).fetchall()
        print(f"Columns for {schema}.{table}:")
        for c in cols:
            print(f" - {c.column_name} :: {c.data_type} (nullable={c.is_nullable})")

        print("\nFirst 10 rows:")
        rows = conn.execute(text(f'SELECT * FROM "{schema}"."{table}" LIMIT 10')).fetchall()
        for r in rows:
            print(dict(r._mapping))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m data.peek_table <schema.table>')
        sys.exit(2)
    peek(sys.argv[1])
