# THIS FILE IS ONLY FOR TESTING PURPOSES (BG)
from __future__ import annotations
from pathlib import Path
import sys
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()
from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# -------------------- helpers --------------------

def table_columns_meta(conn, schema: str, table: str):
    """
    Returns list of dicts:
    {column_name, data_type, is_nullable ('YES'/'NO'), column_default}
    """
    rows = conn.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
    """), {"schema": schema, "table": table}).fetchall()
    return [dict(r._mapping) for r in rows]

def primary_key_columns(conn, schema: str, table: str) -> list[str]:
    rows = conn.execute(text("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
        WHERE n.nspname = :schema AND c.relname = :table AND i.indisprimary
        ORDER BY a.attnum
    """), {"schema": schema, "table": table}).fetchall()
    return [r[0] for r in rows]

def detect_movie_id_col(conn) -> str:
    cols = [c["column_name"] for c in table_columns_meta(conn, "public", "movies")]
    if not cols:
        raise RuntimeError("public.movies not found")
    pks = primary_key_columns(conn, "public", "movies")
    if "movie_id" in cols: return "movie_id"
    if "id" in cols: return "id"
    if pks: return pks[0]
    return cols[0]

def detect_movie_title_col(conn) -> str | None:
    cols = {c["column_name"] for c in table_columns_meta(conn, "public", "movies")}
    if "title" in cols: return "title"
    if "name" in cols: return "name"
    return None

def detect_user_id_col(conn) -> str:
    cols = [c["column_name"] for c in table_columns_meta(conn, "public", "users")]
    if not cols:
        raise RuntimeError("public.users not found")
    pks = primary_key_columns(conn, "public", "users")
    if "user_id" in cols: return "user_id"
    if "id" in cols: return "id"
    if pks: return pks[0]
    return cols[0]

def required_user_cols(conn) -> list[dict]:
    """
    Return columns that are NOT NULL and have NO DEFAULT (so we must provide a value).
    """
    meta = table_columns_meta(conn, "public", "users")
    req = []
    for col in meta:
        not_null = (col["is_nullable"] == "NO")
        has_default = (col["column_default"] is not None)
        if not_null and not has_default:
            req.append(col)
    return req

def default_value_for(colname: str, dtype: str, user_id_val: int):
    """
    Produce a parameter value for a required column based on its type/name.
    For timestamps, return a special marker so we can put NOW() directly into SQL.
    """
    dtype = dtype.lower()
    name = colname.lower()

    if "email" in name:
        return f"user{user_id_val}@example.com"
    if dtype in ("text", "character varying", "character", "citext"):
        # Common usernames / names
        if "username" in name: return f"user{user_id_val}"
        if "name" in name: return f"user{user_id_val}"
        return f"val_{user_id_val}"
    if dtype in ("bigint", "integer", "smallint", "numeric", "real", "double precision"):
        return user_id_val
    if "bool" in dtype:
        return False
    if dtype.startswith("timestamp"):
        return "__NOW__"
    if dtype in ("uuid",):
        
        return f"00000000-0000-0000-0000-{user_id_val:012d}"[-36:]
    return f"v_{user_id_val}"

def detect_vector_dims(conn) -> int | None:
    row = conn.execute(text("""
        SELECT format_type(a.atttypid, a.atttypmod) AS type_str
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'item_embeddings' AND a.attname = 'embedding'
    """)).fetchone()
    if not row:
        return None
    type_str = row[0] or ""
    import re
    m = re.search(r"vector\((\d+)\)", type_str)
    if m:
        return int(m.group(1))
    return None

# -------------------- seeding --------------------

def main():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        movie_id_col = detect_movie_id_col(conn)
        movie_title_col = detect_movie_title_col(conn)
        movies = [
            (1, "Toy Story"),
            (2, "The Matrix"),
            (3, "Inception"),
            (4, "Finding Nemo"),
            (5, "Interstellar"),
        ]
        for mid, title in movies:
            if movie_title_col:
                conn.execute(text(f"""
                    INSERT INTO public.movies ({movie_id_col}, {movie_title_col})
                    VALUES (:mid, :title)
                    ON CONFLICT ({movie_id_col}) DO UPDATE SET {movie_title_col} = EXCLUDED.{movie_title_col}
                """), {"mid": mid, "title": title})
            else:
                conn.execute(text(f"""
                    INSERT INTO public.movies ({movie_id_col})
                    VALUES (:mid)
                    ON CONFLICT ({movie_id_col}) DO NOTHING
                """), {"mid": mid})

        user_id_col = detect_user_id_col(conn)
        users_to_insert = [101, 102]

        req_cols = required_user_cols(conn)
        need_names = {c["column_name"] for c in req_cols}
        if user_id_col not in need_names:
            pass

        for uid in users_to_insert:
            col_vals = {user_id_col: uid}
            for col in req_cols:
                name = col["column_name"]
                if name == user_id_col:
                    continue
                val = default_value_for(name, col["data_type"], uid)
                col_vals[name] = val

            cols = list(col_vals.keys())
            values_sql = []
            params = {}
            for name in cols:
                v = col_vals[name]
                if v == "__NOW__":
                    values_sql.append("NOW()")
                else:
                    values_sql.append(f":{name}")
                    params[name] = v

            cols_sql = ", ".join(f'"{c}"' for c in cols)
            vals_sql = ", ".join(values_sql)

            insert_sql = text(f"""
                INSERT INTO public.users ({cols_sql})
                VALUES ({vals_sql})
                ON CONFLICT ("{user_id_col}") DO NOTHING
            """)
            conn.execute(insert_sql, params)

        interactions = [
            (101, 1, 5.0, "rating", 1.0),
            (101, 2, 4.5, "rating", 1.0),
            (101, 4, 4.0, "rating", 1.0),
            (102, 3, 5.0, "rating", 1.0),
            (102, 5, 4.5, "rating", 1.0),
        ]
        for uid, mid, r, itype, w in interactions:
            conn.execute(text("""
                INSERT INTO public.interactions (user_id, movie_id, rating, interaction_type, weight, interacted_at)
                VALUES (:uid, :mid, :rating, :itype, :weight, NOW())
                ON CONFLICT DO NOTHING
            """), {"uid": uid, "mid": mid, "rating": r, "itype": itype, "weight": w})

        dims = detect_vector_dims(conn) or 64
        rng = np.random.default_rng(42)

        for mid, _ in movies:
            vec = rng.normal(size=dims)
            n = np.linalg.norm(vec)
            if n > 0:
                vec = vec / n
            vec_str = "[" + ", ".join(f"{x:.6f}" for x in vec) + "]"
            conn.execute(text("""
                INSERT INTO public.item_embeddings (movie_id, embedding, updated_at)
                VALUES (:mid, CAST(:vec AS vector), NOW())
                ON CONFLICT (movie_id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    updated_at = NOW()
            """), {"mid": mid, "vec": vec_str})

        print(f"✅ Seed complete. Inserted/updated {len(movies)} movies, {len(users_to_insert)} users, "
              f"{len(interactions)} interactions, and {len(movies)} embeddings (dim={dims}).")

if __name__ == "__main__":
    main()
